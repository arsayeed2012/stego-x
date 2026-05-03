"""
╔═══════════════════════════════════════════════════════╗
║           STEGO-X  |  Covert Channel Toolkit          ║
║       LSB Steganography — Attack & Defense Lab        ║
║              For educational use only                 ║
╚═══════════════════════════════════════════════════════╝

stego.py — unified CLI: encode, decode, analyze
Requirements: pip install Pillow rich
"""

from PIL import Image
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.text import Text
from rich.align import Align
from rich import box
from rich.columns import Columns
import hashlib
import argparse
import time
import sys
import os

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
#  BANNER
# ─────────────────────────────────────────────────────────────────────────────

BANNER = r"""
  ██████ ▄▄▄█████▓▓█████  ▄████  ▒█████      ▒██   ██▒
▒██    ▒ ▓  ██▒ ▓▒▓█   ▀ ██▒ ▀█▒▒██▒  ██▒     ▒▒ █ █ ▒░
░ ▓██▄   ▒ ▓██░ ▒░▒███  ▒██░▄▄▄░▒██░  ██▒     ░░  █   ░
  ▒   ██▒░ ▓██▓ ░ ▒▓█  ▄░▓█  ██▓▒██   ██░      ░ █ █ ▒
▒██████▒▒  ▒██▒ ░ ░▒████▒░▒▓███▀▒░ ████▓▒░    ▒██▒ ▒██▒
▒ ▒▓▒ ▒ ░  ▒ ░░   ░░ ▒░ ░ ░▒   ▒ ░ ▒░▒░▒░     ▒▒ ░ ░▓ ░
░ ░▒  ░ ░    ░     ░ ░  ░  ░   ░   ░ ▒ ▒░     ░░   ░▒ ░
░  ░  ░    ░         ░   ░ ░   ░ ░ ░ ░ ▒       ░    ░
      ░               ░  ░      ░     ░ ░       ░    ░
"""

def print_banner():
    console.print(f"[bold green]{BANNER}[/bold green]")
    console.print(
        Align.center(
            "[dim][ Covert Channel Toolkit · LSB Engine · Attack/Defense Lab ][/dim]\n"
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def bytes_to_bits(data: bytes) -> list[int]:
    return [(byte >> i) & 1 for byte in data for i in range(7, -1, -1)]

def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        out.append(byte)
    return bytes(out)


# ─────────────────────────────────────────────────────────────────────────────
#  ENCODE — hide payload inside cover image
# ─────────────────────────────────────────────────────────────────────────────

def encode(cover_path: str, output_path: str, payload: bytes):
    print_banner()

    if Path(output_path).suffix.lower() not in ('.png', '.bmp'):
        console.print(Panel(
            "[bold red]✗ Output must be .png or .bmp\n"
            "[dim]JPEG/WebP re-quantize pixel data — LSB bits destroyed on save.[/dim]",
            title="[red]FORMAT ERROR[/red]", border_style="red"
        ))
        sys.exit(1)

    console.print(Panel(
        f"[bold cyan]OPERATION:[/bold cyan] [green]ENCODE (INJECT)[/green]\n"
        f"[bold cyan]COVER    :[/bold cyan] {cover_path}\n"
        f"[bold cyan]OUTPUT   :[/bold cyan] {output_path}\n"
        f"[bold cyan]PAYLOAD  :[/bold cyan] {len(payload)} bytes",
        title="[bold green][ MISSION PARAMETERS ][/bold green]",
        border_style="green"
    ))

    console.print("\n[bold yellow]► Loading cover image...[/bold yellow]")
    img = Image.open(cover_path).convert('RGB')
    width, height = img.size
    pixels = list(img.getdata())

    capacity_bits  = width * height * 3
    required_bits  = 32 + len(payload) * 8
    capacity_bytes = capacity_bits // 8

    # Capacity table
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold green")
    tbl.add_column("METRIC",     style="cyan",  width=22)
    tbl.add_column("VALUE",      style="white", width=24)
    tbl.add_column("STATUS",     style="green", width=14)

    used_pct = required_bits / capacity_bits * 100
    status   = "[green]OK[/green]" if used_pct < 75 else "[yellow]HIGH[/yellow]" if used_pct < 90 else "[red]CRITICAL[/red]"

    tbl.add_row("Dimensions",      f"{width} x {height} px",          "[green]✓[/green]")
    tbl.add_row("Cover capacity",  f"{capacity_bytes:,} bytes",        "[green]✓[/green]")
    tbl.add_row("Payload size",    f"{len(payload):,} bytes",          "[green]✓[/green]")
    tbl.add_row("Capacity used",   f"{used_pct:.2f}%",                 status)
    tbl.add_row("Payload SHA-256", sha256(payload)[:32] + "...",       "[green]✓[/green]")
    console.print(tbl)

    if required_bits > capacity_bits:
        console.print("[bold red]✗ PAYLOAD TOO LARGE — choose a bigger cover image.[/bold red]")
        sys.exit(1)

    bit_stream = bytes_to_bits(len(payload).to_bytes(4, 'big') + payload)
    new_pixels = []
    bit_idx    = 0
    total      = len(bit_stream)

    console.print("\n[bold yellow]► Injecting payload into LSB layer...[/bold yellow]")

    with Progress(
        TextColumn("[bold green]{task.description}"),
        BarColumn(bar_width=45, style="green", complete_style="bright_green"),
        TextColumn("[cyan]{task.percentage:>5.1f}%[/cyan]"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[bold green]ENCODING", total=len(pixels))
        for pixel in pixels:
            if bit_idx >= total:
                new_pixels.append(pixel)
            else:
                nc = []
                for channel in pixel:
                    if bit_idx < total:
                        nc.append((channel & 0xFE) | bit_stream[bit_idx])
                        bit_idx += 1
                    else:
                        nc.append(channel)
                new_pixels.append(tuple(nc))
            progress.advance(task)

    console.print("\n[bold yellow]► Writing stego image to disk...[/bold yellow]")
    out = Image.new('RGB', (width, height))
    out.putdata(new_pixels)
    out.save(output_path)

    # File size delta (an IOC a defender would catch)
    orig_size  = os.path.getsize(cover_path)
    stego_size = os.path.getsize(output_path)
    delta      = stego_size - orig_size

    console.print(Panel(
        f"[bold green]✓ PAYLOAD INJECTED SUCCESSFULLY[/bold green]\n\n"
        f"  [cyan]Output file   :[/cyan] {output_path}\n"
        f"  [cyan]Payload hash  :[/cyan] [dim]{sha256(payload)}[/dim]\n"
        f"  [cyan]Cover size    :[/cyan] {orig_size:,} bytes\n"
        f"  [cyan]Stego size    :[/cyan] {stego_size:,} bytes\n"
        f"  [cyan]Size delta    :[/cyan] [yellow]+{delta} bytes[/yellow] [dim](← IOC: defenders watch for this)[/dim]\n"
        f"  [cyan]Bits used     :[/cyan] {required_bits:,} / {capacity_bits:,} "
        f"([yellow]{used_pct:.2f}%[/yellow])",
        title="[bold green][ OPERATION COMPLETE ][/bold green]",
        border_style="green"
    ))


# ─────────────────────────────────────────────────────────────────────────────
#  DECODE — extract hidden payload
# ─────────────────────────────────────────────────────────────────────────────

def decode(stego_path: str, output_file: str = None, as_text: bool = False):
    print_banner()

    console.print(Panel(
        f"[bold cyan]OPERATION:[/bold cyan] [yellow]DECODE (EXTRACT)[/yellow]\n"
        f"[bold cyan]TARGET   :[/bold cyan] {stego_path}",
        title="[bold yellow][ EXTRACTION PARAMETERS ][/bold yellow]",
        border_style="yellow"
    ))

    console.print("\n[bold yellow]► Scanning LSB layer...[/bold yellow]")
    img  = Image.open(stego_path).convert('RGB')
    bits = []

    with Progress(
        TextColumn("[bold yellow]{task.description}"),
        BarColumn(bar_width=45, style="yellow", complete_style="bright_yellow"),
        TextColumn("[cyan]{task.percentage:>5.1f}%[/cyan]"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        data   = list(img.getdata())
        task   = progress.add_task("[bold yellow]SCANNING", total=len(data))
        for pixel in data:
            for c in pixel:
                bits.append(c & 1)
            progress.advance(task)

    if len(bits) < 32:
        console.print("[bold red]✗ Image too small — no hidden data.[/bold red]")
        sys.exit(1)

    length    = int(''.join(map(str, bits[:32])), 2)
    available = (len(bits) - 32) // 8

    if length == 0 or length > available:
        console.print(Panel(
            "[bold red]✗ NO HIDDEN PAYLOAD DETECTED[/bold red]\n\n"
            f"  Header value  : {length} bytes\n"
            f"  Available     : {available} bytes\n\n"
            "[dim]Image appears clean — or uses a different stego scheme.[/dim]",
            title="[bold red][ EXTRACTION FAILED ][/bold red]",
            border_style="red"
        ))
        sys.exit(1)

    console.print(f"\n[bold green]► Header decoded — payload size: [yellow]{length}[/yellow] bytes[/bold green]")
    console.print("[bold yellow]► Reconstructing payload bits...[/bold yellow]")

    payload = bits_to_bytes(bits[32:32 + length * 8])

    console.print(Panel(
        f"[bold green]✓ PAYLOAD EXTRACTED SUCCESSFULLY[/bold green]\n\n"
        f"  [cyan]Size          :[/cyan] {len(payload):,} bytes\n"
        f"  [cyan]SHA-256       :[/cyan] [dim]{sha256(payload)}[/dim]\n"
        f"  [cyan]Hex preview   :[/cyan] [yellow]{payload[:32].hex()}[/yellow][dim]...[/dim]",
        title="[bold green][ EXTRACTION COMPLETE ][/bold green]",
        border_style="green"
    ))

    if as_text:
        try:
            decoded = payload.decode('utf-8')
            console.print(Panel(
                f"[bold white]{decoded}[/bold white]",
                title="[bold cyan][ HIDDEN MESSAGE ][/bold cyan]",
                border_style="cyan"
            ))
        except UnicodeDecodeError:
            console.print("[yellow]⚠ Payload is binary — use --output-file to save.[/yellow]")

    if output_file:
        Path(output_file).write_bytes(payload)
        console.print(f"\n[bold green]✓ Payload written to:[/bold green] {output_file}")

    return payload


# ─────────────────────────────────────────────────────────────────────────────
#  ANALYZE — defender mode: inspect image for IOCs
# ─────────────────────────────────────────────────────────────────────────────

def analyze(image_path: str):
    print_banner()

    console.print(Panel(
        f"[bold cyan]OPERATION:[/bold cyan] [red]ANALYZE (DETECT)[/red]\n"
        f"[bold cyan]TARGET   :[/bold cyan] {image_path}",
        title="[bold red][ ANALYST MODE ][/bold red]",
        border_style="red"
    ))

    img        = Image.open(image_path).convert('RGB')
    w, h       = img.size
    pixels     = list(img.getdata())
    total_px   = w * h
    file_size  = os.path.getsize(image_path)

    # ── LSB distribution (clean images = ~50% 0s and 1s in LSBs)
    console.print("\n[bold red]► Running LSB entropy analysis...[/bold red]")
    lsb_counts = {0: 0, 1: 0}
    for pixel in pixels:
        for c in pixel:
            lsb_counts[c & 1] += 1

    total_bits = total_px * 3
    ratio_0    = lsb_counts[0] / total_bits
    ratio_1    = lsb_counts[1] / total_bits
    deviation  = abs(ratio_0 - 0.5)

    # ── Chi-square approximation (simplified)
    # In an unmodified image, LSBs follow camera noise distribution (not 50/50)
    # After LSB injection, distribution skews toward 50/50 — that's the tell
    expected   = total_bits / 2
    chi_sq     = ((lsb_counts[0] - expected)**2 / expected) + \
                 ((lsb_counts[1] - expected)**2 / expected)

    # ── Read header to check for our tool's signature
    bits        = [c & 1 for pixel in pixels for c in pixel]
    header_val  = int(''.join(map(str, bits[:32])), 2)
    has_payload = 0 < header_val <= (total_bits - 32) // 8

    # ── Expected file size vs actual (rough heuristic for PNG)
    # PNG compresses well; high LSB entropy → worse compression → bigger file
    expected_size = total_px * 3 * 0.4   # typical PNG compression ratio ~40%
    size_ratio    = file_size / max(expected_size, 1)

    # ─── Results table
    results = Table(box=box.DOUBLE_EDGE, show_header=True, header_style="bold red",
                    title="[bold red]▓ IOC ANALYSIS REPORT ▓[/bold red]",
                    title_style="bold red")
    results.add_column("INDICATOR",   style="cyan",  width=28)
    results.add_column("VALUE",       style="white", width=26)
    results.add_column("VERDICT",     style="bold",  width=20)

    def verdict(condition, true_msg="[red]⚠ SUSPICIOUS[/red]", false_msg="[green]✓ CLEAN[/green]"):
        return true_msg if condition else false_msg

    results.add_row("Dimensions",
                    f"{w} × {h}",
                    "[green]✓ OK[/green]")
    results.add_row("File size",
                    f"{file_size:,} bytes",
                    verdict(size_ratio > 0.7, "[yellow]⚠ LARGE[/yellow]", "[green]✓ NORMAL[/green]"))
    results.add_row("LSB bit ratio (0s)",
                    f"{ratio_0:.4f}  (ideal: 0.5000)",
                    verdict(deviation < 0.01))
    results.add_row("LSB bit ratio (1s)",
                    f"{ratio_1:.4f}",
                    verdict(deviation < 0.01))
    results.add_row("Chi-square score",
                    f"{chi_sq:.2f}  (< 3.84 = clean)",
                    verdict(chi_sq < 3.84,
                            "[green]✓ NATURAL DIST[/green]",
                            "[red]⚠ MODIFIED DIST[/red]"))
    results.add_row("Header signature",
                    f"{header_val} bytes declared",
                    verdict(has_payload,
                            "[bold red]✗ PAYLOAD FOUND[/bold red]",
                            "[green]✓ NO SIGNATURE[/green]"))

    console.print()
    console.print(results)

    # ── Final verdict
    suspicious_count = sum([
        deviation < 0.01,
        chi_sq < 3.84,
        has_payload,
        size_ratio > 0.7
    ])

    if suspicious_count >= 3:
        verdict_panel = Panel(
            "[bold red]✗ HIGH CONFIDENCE — STEGO PAYLOAD DETECTED[/bold red]\n\n"
            f"  {suspicious_count}/4 indicators triggered\n"
            "  Recommend: quarantine image, extract with decoder, hash and document.\n"
            "  Run [bold]zsteg[/bold], [bold]binwalk[/bold], [bold]exiftool[/bold] for confirmation.",
            title="[bold red][ THREAT DETECTED ][/bold red]",
            border_style="red"
        )
    elif suspicious_count >= 2:
        verdict_panel = Panel(
            "[bold yellow]⚠ MEDIUM CONFIDENCE — INCONCLUSIVE[/bold yellow]\n\n"
            f"  {suspicious_count}/4 indicators triggered\n"
            "  Recommend: deeper analysis with zsteg / stegsolve.",
            title="[bold yellow][ FURTHER ANALYSIS NEEDED ][/bold yellow]",
            border_style="yellow"
        )
    else:
        verdict_panel = Panel(
            "[bold green]✓ LOW CONFIDENCE — IMAGE APPEARS CLEAN[/bold green]\n\n"
            f"  {suspicious_count}/4 indicators triggered\n"
            "  [dim]Note: absence of detection ≠ absence of payload.[/dim]\n"
            "  Advanced schemes (JPEG DCT, palette) not covered by this tool.",
            title="[bold green][ NO THREAT DETECTED ][/bold green]",
            border_style="green"
        )

    console.print()
    console.print(verdict_panel)

    # ── Suggested next commands
    console.print(Panel(
        "[bold cyan]NEXT STEPS (Kali Linux):[/bold cyan]\n\n"
        f"  [yellow]$[/yellow] zsteg {image_path}\n"
        f"  [yellow]$[/yellow] binwalk -e {image_path}\n"
        f"  [yellow]$[/yellow] exiftool {image_path}\n"
        f"  [yellow]$[/yellow] python stego.py decode --stego {image_path} --text",
        title="[bold cyan][ ANALYST PLAYBOOK ][/bold cyan]",
        border_style="cyan"
    ))


# ─────────────────────────────────────────────────────────────────────────────
#  CAPACITY — show how much a cover image can hold
# ─────────────────────────────────────────────────────────────────────────────

def capacity(image_path: str):
    print_banner()
    img       = Image.open(image_path).convert('RGB')
    w, h      = img.size
    px        = w * h

    tbl = Table(box=box.DOUBLE_EDGE, header_style="bold green",
                title=f"[bold green]▓ CAPACITY REPORT — {Path(image_path).name} ▓[/bold green]")
    tbl.add_column("LSB DEPTH",   style="cyan",   width=14)
    tbl.add_column("CAPACITY",    style="white",  width=18)
    tbl.add_column("DETECTABILITY", style="bold", width=22)

    tbl.add_row("1-bit LSB", f"{px*3//8:,} bytes ({px*3//8//1024:.0f} KB)",
                "[green]Low — near-invisible[/green]")
    tbl.add_row("2-bit LSB", f"{px*6//8:,} bytes ({px*6//8//1024:.0f} KB)",
                "[yellow]Medium — subtle noise[/yellow]")
    tbl.add_row("4-bit LSB", f"{px*12//8:,} bytes ({px*12//8//1024:.0f} KB)",
                "[red]High — visible artifacts[/red]")

    console.print()
    console.print(tbl)
    console.print(
        f"\n[dim]  Image: {w}×{h} | {px:,} total pixels | "
        f"File: {os.path.getsize(image_path):,} bytes[/dim]\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='STEGO-X | Covert Channel Toolkit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  encode    Hide a message or file inside a cover image
  decode    Extract hidden payload from a stego image
  analyze   Run IOC detection on a suspicious image
  capacity  Show how much data a cover image can hold

examples:
  python stego.py encode --cover cover.png --output out.png --message "secret"
  python stego.py encode --cover cover.png --output out.png --file payload.txt
  python stego.py decode --stego out.png --text
  python stego.py decode --stego out.png --output-file recovered.txt
  python stego.py analyze --image suspicious.png
  python stego.py capacity --image cover.png
        """
    )
    sub = parser.add_subparsers(dest='command')

    # encode
    enc = sub.add_parser('encode')
    enc.add_argument('--cover',   required=True)
    enc.add_argument('--output',  required=True)
    g = enc.add_mutually_exclusive_group(required=True)
    g.add_argument('--message')
    g.add_argument('--file')

    # decode
    dec = sub.add_parser('decode')
    dec.add_argument('--stego',       required=True)
    dec.add_argument('--output-file')
    dec.add_argument('--text',        action='store_true')

    # analyze
    ana = sub.add_parser('analyze')
    ana.add_argument('--image', required=True)

    # capacity
    cap = sub.add_parser('capacity')
    cap.add_argument('--image', required=True)

    args = parser.parse_args()

    if args.command == 'encode':
        payload = args.message.encode('utf-8') if args.message else Path(args.file).read_bytes()
        encode(args.cover, args.output, payload)
    elif args.command == 'decode':
        decode(args.stego, args.output_file, args.text)
    elif args.command == 'analyze':
        analyze(args.image)
    elif args.command == 'capacity':
        capacity(args.image)
    else:
        print_banner()
        parser.print_help()


if __name__ == '__main__':
    main()
