# Stego-X: Covert Channel Simulation & Detection Lab

> A beginner-to-intermediate cybersecurity project simulating a full **LSB steganography attack chain** — from payload encoding to drive-by exfiltration — with a live C2 terminal dashboard. Built entirely in Python. No APK. No install. No clicks from the victim.

---

## What This Project Demonstrates

| Perspective | What Was Built |
|---|---|
| **Attacker (Red Team)** | LSB encoder hiding commands in PNG images, fake website, drive-by JS attack, cookie theft, autofill harvesting, localStorage dump |
| **Victim** | Android emulator (Pixel 3a, API 28) browsing a realistic fake wallpaper site |
| **Defender (Blue Team)** | Chi-square LSB detection, file size anomaly analysis, zsteg/binwalk/exiftool usage, IOC identification |

---

## Full Attack Chain

```
[Attacker - Windows/Kali]
    │
    ▼
python stego.py encode
  └── Hides "CMD:STEAL_DEVICE_INFO" inside a normal PNG
      using LSB (Least Significant Bit) substitution
    │
    ▼
python c2_server.py
  └── Starts a fake "WallpaperHD" website
  └── Serves the stego image silently
  └── Opens a live terminal dashboard
    │
    ▼ (victim opens Chrome on Android emulator)
    │
    ▼
http://10.0.2.2:8080/setup
  └── Plants fake session cookies + localStorage data
  └── Auto-redirects to main attack page
    │
    ▼
http://10.0.2.2:8080
  └── JS fetches stego image silently
  └── Decodes hidden LSB payload (client-side)
  └── Reads cookies, localStorage, sessionStorage
  └── Runs autofill trap (password manager harvesting)
  └── Collects device fingerprint (GPU, RAM, CPU, timezone...)
  └── POSTs everything to /collect
    │
    ▼
[C2 Dashboard goes RED]
  └── Shows: hidden command, cookies, storage, fingerprint
  └── Real-time. No refresh needed.
```

---

## Project Structure

```
stego-lab/
├── stego.py          # LSB encoder / decoder / analyzer / capacity checker
├── c2_server.py      # Full C2 server with live Rich dashboard
├── samples/
│   ├── cover.png     # Original cover image
│   └── stego.png     # Stego image (payload hidden inside)
└── README.md
```

---

## Tools & Stack

| Tool | Purpose |
|---|---|
| Python 3.11+ | Core language |
| Pillow | Image pixel manipulation (LSB encoding/decoding) |
| Rich | Live terminal dashboard, colored output, progress bars |
| Android Studio | Pixel 3a emulator (API 28) as victim device |
| zsteg | LSB detection (Kali Linux) |
| binwalk | Embedded file detection |
| exiftool | Metadata analysis |

---

## Setup & Usage

### Requirements
```bash
pip install Pillow rich
```

### Step 1 — Encode a hidden payload into an image
```bash
python stego.py encode \
  --cover samples/cover.png \
  --output samples/stego.png \
  --message "CMD:STEAL_DEVICE_INFO|op=silent|target=victim_001"
```

### Step 2 — Verify it works (decode)
```bash
python stego.py decode --stego samples/stego.png --text
```

### Step 3 — Check capacity
```bash
python stego.py capacity --image samples/cover.png
```

### Step 4 — Analyze for IOCs (defender mode)
```bash
python stego.py analyze --image samples/stego.png
```

### Step 5 — Start the C2 server
```bash
python c2_server.py --image samples/stego.png --port 8080
```

### Step 6 — Open on Android emulator
```
Open Chrome in emulator
Go to: http://10.0.2.2:8080/setup
Watch the C2 dashboard go red.
```

---

## C2 Server Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/setup` | GET | Plants cookies + localStorage, auto-redirects |
| `/` | GET | Main attack page (fake wallpaper site) |
| `/wallpaper.png` | GET | Serves the stego image |
| `/api/cmd` | GET | Returns decoded payload as JSON |
| `/collect` | POST | Receives exfiltrated data |

---

## What Gets Exfiltrated

```
-- STEGO COMMAND --
Hidden payload decoded from PNG via LSB

-- COOKIES --
All non-HttpOnly cookies readable by JavaScript

-- LOCAL STORAGE --
Full localStorage + sessionStorage dump

-- DEVICE FINGERPRINT --
Screen resolution, GPU renderer, CPU cores,
RAM, timezone, language, connection type,
touch points, browser, platform
```

---

## Detection (Defender / Blue Team)

### Using stego.py analyze
```bash
python stego.py analyze --image samples/stego.png
```
Runs chi-square test, LSB distribution analysis,
header signature detection, file size anomaly check.

### Using Kali Linux tools
```bash
zsteg samples/stego.png          # LSB analysis — catches it
binwalk -e samples/stego.png     # embedded file detection
exiftool samples/stego.png       # metadata inspection
```

### IOC Indicators
- Stego image slightly larger than expected for its dimensions
- LSB chi-square score below 3.84 (near-perfect 50/50 distribution)
- Header signature found at bit position 0
- Image served from unusual domain with no prior history

---

## Problems I Faced & How I Solved Them

### Problem 1 — JPEG destroys LSB data
JPEG uses lossy DCT compression. Saving a stego image as JPEG
re-quantizes pixel values and destroys the hidden bits entirely.

**Fix:** Enforce PNG/BMP output only. Added format validation
in the encoder with a clear error message.

### Problem 2 — Chrome canvas taint restriction
Chrome blocks `getImageData()` on images loaded via blob URLs
due to its security sandbox. The JS decoder was silently failing —
the POST never arrived at the C2 server.

**Fix:** Added `/api/cmd` as a guaranteed fallback endpoint.
The server decodes the stego payload in Python and serves it as JSON.
JS fetches this directly — no canvas needed. The canvas decode
still runs in parallel as a bonus.

### Problem 3 — Python SyntaxError with JS template literals
JavaScript backtick template literals (`${variable}`) inside
Python triple-quoted strings caused `SyntaxError: invalid decimal literal`.

**Fix:** Replaced all JS template literals with string concatenation.
`"linear-gradient(" + color1 + "," + color2 + ")"` instead of
backtick syntax. Also moved all HTML into Python string concatenation
to avoid any quoting conflicts.

### Problem 4 — bytes literal with non-ASCII characters
Using `b"""..."""` (bytes literal) for the HTML setup page caused
`SyntaxError: bytes can only contain ASCII literal characters`
because the HTML contained Unicode symbols.

**Fix:** Changed to a regular string and called `.encode("utf-8")`
when writing to the HTTP response. All HTML is now stored as str
and encoded at send time.

### Problem 5 — Emulator browser going to wrong URL
The emulator was navigating to `/download` (leftover from an earlier
APK-based version) instead of the root attack page.

**Fix:** Removed the APK delivery approach entirely in favor of
a pure drive-by attack. No APK needed. The attack fires the moment
the victim opens the main page — no install, no permission, no click.

### Problem 6 — Cookies were empty in the exfil panel
The Android emulator browser was a fresh install with no stored
cookies or passwords, so the exfil showed empty credential fields.

**Fix:** Built the `/setup` endpoint. It plants realistic fake
session cookies (server-side via Set-Cookie headers) and localStorage
data (client-side via JS) before redirecting to the attack page.
This simulates a victim who already has an active session.

---

## Why This Can't Steal Photos or Contacts

A browser-based drive-by attack is limited to what JavaScript
can access inside the browser sandbox:

| What JS Can Access | What JS Cannot Access |
|---|---|
| Cookies (non-HttpOnly) | Camera roll / photos |
| localStorage / sessionStorage | Video files |
| Device fingerprint | Contacts / SMS |
| Autofill fields | File system |
| Browser history (limited) | GPS (requires permission prompt) |

To access photos or contacts a native Android APK is required,
which must explicitly request `READ_EXTERNAL_STORAGE` and
`READ_CONTACTS` permissions — and the user must tap Allow.
This is why real spyware is always distributed as an APK,
not a webpage.

---

## How Attackers Bypass HTTPS Warnings (Real World)

| Method | How |
|---|---|
| Let's Encrypt | Free SSL cert, issued in minutes, no content review |
| Lookalike domains | googie.com, g00gle.com — all with valid certs |
| Compromised sites | Inject JS into already-trusted HTTPS sites |
| SSL stripping | bettercap on local network downgrades HTTPS to HTTP |
| Corporate networks | Internal HTTP tools, no SSL inspection |

In this lab, HTTP works fine because `10.0.2.2` is treated
as a local address by Chrome — no HTTPS warning.

---

## LinkedIn Post

> Built a full steganography C2 simulation from scratch.
>
> Attack chain:
> Hidden command encoded into a PNG using LSB steganography.
> Fake website serves the image silently to an Android emulator.
> JavaScript decodes the hidden payload client-side.
> Collects cookies, localStorage, device fingerprint.
> Exfiltrates everything to a live terminal dashboard.
> Zero clicks. Zero installs. Pure drive-by.
>
> Then built the detection side using chi-square analysis,
> LSB distribution scanning, and Kali Linux tooling.
>
> Full write-up and code on GitHub.
>
> #CyberSecurity #Python #BlueTeam #RedTeam #SOC #Steganography

---

## Future Improvements

- Add HTTPS with self-signed cert (pyopenssl)
- Add YARA rule for detecting this stego scheme
- Machine learning LSB anomaly detector (sklearn)
- Multi-image payload distribution (split across N images)
- Add Kali-side detection phase screen recording

---

## Legal & Ethics

This project was built entirely in a local isolated lab environment.
All attack simulations target only systems I own (Android emulator).
No real credentials, cookies, or personal data were collected.
This is for educational and portfolio purposes only.
