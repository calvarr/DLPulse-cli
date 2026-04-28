"""
DLPulse — CLI argument handler.

Apelat din main() în dlpulse_cli.py.
Dacă sys.argv are argumente → rulează comanda non-interactiv și iese.
Dacă sys.argv e gol → returnează False → main() pornește TUI-ul.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dlpulse",
        description="DLPulse — YouTube / yt-dlp downloader + Chromecast",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comenzi disponibile:
  search  QUERY              Caută pe YouTube (sau SoundCloud cu --sc)
  download URL [URL ...]     Descarcă video/audio de la un URL
  formats                    Listează formatele disponibile (preset index)
  play    FILE_SAU_URL       Redă cu playerul configurat
  cast    FILE [FILE ...]    Trimite la Chromecast
  config                     Afișează configurația curentă

Exemple:
  dlpulse search "iris goo goo dolls"
  dlpulse search "lofi hip hop" --sc
  dlpulse download https://youtube.com/watch?v=...
  dlpulse download https://youtube.com/watch?v=... --audio
  dlpulse download https://youtube.com/watch?v=... --format 3
  dlpulse download https://youtube.com/watch?v=... --out ~/Muzica
  dlpulse formats
  dlpulse play ~/Downloads/song.mp3
  dlpulse cast ~/Downloads/movie.mp4
  dlpulse config
        """,
    )

    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    # ── search ──────────────────────────────────────────────────────────────
    ps = sub.add_parser("search", help="Caută pe YouTube (sau SoundCloud)")
    ps.add_argument("query", nargs="+", help="Termenul de căutare")
    ps.add_argument("--sc", "--soundcloud", action="store_true",
                    help="Caută pe SoundCloud în loc de YouTube")
    ps.add_argument("-n", "--results", type=int, default=15, metavar="N",
                    help="Numărul maxim de rezultate (implicit 15)")
    ps.add_argument("--download", action="store_true",
                    help="Descarcă primul rezultat imediat")
    ps.add_argument("--audio", action="store_true",
                    help="Forțează audio-only la --download")

    # ── download ─────────────────────────────────────────────────────────────
    pd = sub.add_parser("download", help="Descarcă de la URL")
    pd.add_argument("urls", nargs="+", metavar="URL",
                    help="URL-ul de descărcat (se pot da mai multe)")
    pd.add_argument("-f", "--format", type=int, default=0, metavar="IDX",
                    dest="fmt_idx",
                    help="Index preset format (vezi: dlpulse formats). Default: 0")
    pd.add_argument("--audio", action="store_true",
                    help="Shortcut pentru audio-only MP3 (echivalent cu --format 4)")
    pd.add_argument("-o", "--out", metavar="DIR",
                    help="Folder de destinație (default: din config)")
    pd.add_argument("--no-playlist", action="store_true",
                    help="Dacă URL-ul e playlist, descarcă doar videoul specificat")

    # ── formats ──────────────────────────────────────────────────────────────
    sub.add_parser("formats", help="Listează presetele de format disponibile")

    # ── play ─────────────────────────────────────────────────────────────────
    pp = sub.add_parser("play", help="Redă un fișier sau URL cu playerul configurat")
    pp.add_argument("targets", nargs="+", metavar="FILE_SAU_URL",
                    help="Fișier(e) sau URL de redat")
    pp.add_argument("--audio", action="store_true",
                    help="Folosește player-ul de audio în loc de cel de video")

    # ── cast ─────────────────────────────────────────────────────────────────
    pc = sub.add_parser("cast", help="Trimite fișiere la Chromecast")
    pc.add_argument("files", nargs="+", metavar="FILE",
                    help="Fișier(e) de trimis la Chromecast")
    pc.add_argument("-d", "--device", metavar="NUME",
                    help="Filtru după numele device-ului (ex: 'Living')")
    pc.add_argument("-w", "--wait", type=float, default=None, metavar="SEC",
                    help="Timp de descoperire mDNS în secunde")

    # ── config ───────────────────────────────────────────────────────────────
    sub.add_parser("config", help="Afișează configurația curentă")

    return p


def run_cli() -> bool:
    """
    Parsează sys.argv.
    Dacă există o comandă: o execută și returnează True (main() iese).
    Dacă nu există argumente: returnează False (main() pornește TUI).
    """
    if len(sys.argv) < 2:
        return False

    parser = _make_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return True

    # Import-uri lazy — doar dacă avem o comandă
    from rich.console import Console
    from rich.markup import escape
    from rich.table import Table

    console = Console()

    # ── search ────────────────────────────────────────────────────────────────
    if args.command == "search":
        _cmd_search(args, console)

    # ── download ──────────────────────────────────────────────────────────────
    elif args.command == "download":
        _cmd_download(args, console)

    # ── formats ───────────────────────────────────────────────────────────────
    elif args.command == "formats":
        _cmd_formats(console)

    # ── play ──────────────────────────────────────────────────────────────────
    elif args.command == "play":
        _cmd_play(args, console)

    # ── cast ──────────────────────────────────────────────────────────────────
    elif args.command == "cast":
        _cmd_cast(args, console)

    # ── config ────────────────────────────────────────────────────────────────
    elif args.command == "config":
        _cmd_config(console)

    return True


# ══════════════════════════════════════════════════════════════════════════════
# Implementări comenzi
# ══════════════════════════════════════════════════════════════════════════════

def _cmd_search(args, console) -> None:
    from rich.table import Table
    from yt_core import search_youtube, search_soundcloud

    query = " ".join(args.query)
    source = "SoundCloud" if args.sc else "YouTube"
    console.print(f"[cyan]Searching {source}:[/] [bold]{escape(query)}[/] …")

    results = (search_soundcloud if args.sc else search_youtube)(
        query, max_results=args.results
    )

    if not results:
        console.print("[yellow]No results.[/]")
        return

    t = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
    t.add_column("#",     style="dim", width=3)
    t.add_column("Title", no_wrap=False)
    t.add_column("URL",   style="dim cyan", no_wrap=True)

    for i, r in enumerate(results, 1):
        title = r.get("title") or "?"
        url   = r.get("url", "")
        t.add_row(str(i), escape(title), url)

    console.print(t)

    if args.download and results:
        first = results[0]
        console.print(f"\n[cyan]Downloading:[/] {escape(first.get('title','?'))}")
        _do_download(
            urls=[first["url"]],
            fmt_idx=4 if args.audio else 0,
            out_dir=None,
            no_playlist=True,
            console=console,
        )


def _cmd_download(args, console) -> None:
    fmt_idx = 4 if args.audio else args.fmt_idx
    _do_download(
        urls=args.urls,
        fmt_idx=fmt_idx,
        out_dir=args.out,
        no_playlist=args.no_playlist,
        console=console,
    )


def _do_download(
    urls: list[str],
    fmt_idx: int,
    out_dir: str | None,
    no_playlist: bool,
    console,
) -> None:
    from rich.progress import (
        BarColumn, Progress, SpinnerColumn,
        TaskProgressColumn, TextColumn, TimeElapsedColumn,
    )
    from rich.markup import escape
    from yt_core import get_format_preset, run_download
    from dlpulse_config import download_dir_from_config, load_config

    preset = get_format_preset(fmt_idx)
    if not preset:
        console.print(f"[red]Format index {fmt_idx} invalid. Run 'dlpulse formats'.[/]")
        sys.exit(1)

    fmt_spec, opts_extra = preset

    cfg     = load_config()
    out     = out_dir or str(download_dir_from_config(cfg))
    Path(out).mkdir(parents=True, exist_ok=True)

    for url in urls:
        console.print(f"\n[bold cyan]⬇  Downloading:[/] {url}")

        with Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None, complete_style="green", finished_style="green"),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            expand=True,
        ) as progress:
            task = progress.add_task("Starting…", total=100.0)

            def on_progress(d: dict) -> None:
                msg   = str(d.get("message") or "")
                frac  = d.get("fraction")
                title = str(d.get("title") or "").strip()
                desc  = " · ".join(filter(None, [msg, escape(title[:50])]))
                if isinstance(frac, (int, float)):
                    progress.update(task, completed=min(100.0, float(frac) * 100.0), description=desc)
                else:
                    progress.update(task, description=desc)

            import uuid
            job_dir = str(Path(out) / str(uuid.uuid4()))
            Path(job_dir).mkdir(parents=True, exist_ok=True)

            ok, files, err = run_download(
                url, fmt_spec, opts_extra, job_dir,
                no_playlist=no_playlist,
                progress_callback=on_progress,
            )

        if ok:
            for f in files:
                console.print(f"  [green]✓[/]  {escape(f)}")
        else:
            console.print(f"  [red]✗  {escape(err or 'failed')}[/]")
            sys.exit(1)


def _cmd_formats(console) -> None:
    from rich.table import Table
    from yt_core import FORMAT_PRESETS

    t = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
    t.add_column("#",       style="dim", width=3)
    t.add_column("Name",    style="bold")
    t.add_column("Spec",    style="dim")

    for i, (name, spec, *_) in enumerate(FORMAT_PRESETS):
        t.add_row(str(i), name, spec)

    console.print("\n[bold]Available format presets[/]  (use with --format IDX)\n")
    console.print(t)
    console.print("\n[dim]Example: dlpulse download URL --format 4   (audio only)[/]\n")


def _cmd_play(args, console) -> None:
    from dlpulse_config import load_config, KEY_PLAYER_AUDIO, KEY_PLAYER_VIDEO
    import subprocess

    cfg    = load_config()
    player = cfg.get(KEY_PLAYER_AUDIO if args.audio else KEY_PLAYER_VIDEO) or "mpv"

    argv = [player] + list(args.targets)
    console.print(f"[cyan]▶  Playing with {escape(player)}:[/] {' '.join(escape(t) for t in args.targets)}")
    try:
        subprocess.run(argv)
    except FileNotFoundError:
        console.print(f"[red]Player not found: {escape(player)}[/]")
        console.print("[dim]Set KEY_PLAYER_VIDEO / KEY_PLAYER_AUDIO in your config.[/]")
        sys.exit(1)


def _cmd_cast(args, console) -> None:
    from dlpulse_config import load_config, KEY_CAST_DISCOVERY
    from cast_play import stream_url_in_player

    cfg      = load_config()
    wait_s   = args.wait if args.wait is not None else float(cfg.get(KEY_CAST_DISCOVERY, 3))
    dev_filt = (args.device or "").lower()

    console.print(f"[cyan]⊹  Discovering Chromecasts[/] (wait: {wait_s}s) …")

    try:
        import pychromecast
    except ImportError:
        console.print("[red]pychromecast not installed.[/]")
        sys.exit(1)

    chromecasts, browser = pychromecast.get_chromecasts(timeout=wait_s)
    pychromecast.discovery.stop_discovery(browser)

    if not chromecasts:
        console.print("[yellow]No Chromecasts found.[/]")
        sys.exit(1)

    # Filter by name
    targets = (
        [c for c in chromecasts if dev_filt in c.cast_info.friendly_name.lower()]
        if dev_filt else chromecasts
    )

    if not targets:
        console.print(f"[yellow]No device matching '{args.device}'.[/]")
        console.print("[dim]Available:[/] " + ", ".join(c.cast_info.friendly_name for c in chromecasts))
        sys.exit(1)

    cast = targets[0]
    cast.wait()
    console.print(f"[green]●  Casting to:[/] {cast.cast_info.friendly_name}")

    # Start local HTTP server to serve the file
    from cast_http import start_cast_server, media_url, guess_mime_for_cast
    from chromecast_helper import get_lan_ip, play_url

    port = start_cast_server()
    ip   = get_lan_ip()

    for f in args.files:
        p    = Path(f)
        rel  = p.name
        url  = media_url(str(p), ip, port)
        mime = guess_mime_for_cast(rel)
        console.print(f"  [cyan]→[/] {escape(rel)}  ({mime})")
        play_url(cast, url, mime)
        import time; time.sleep(2)  # mic delay între fișiere

    console.print("[green]✓  Done.[/]")


def _cmd_config(console) -> None:
    from rich.table import Table
    from rich.markup import escape
    from dlpulse_config import load_config, config_path_display, download_dir_from_config

    cfg = load_config()
    dl  = download_dir_from_config(cfg)

    console.print(f"\n[bold cyan]DLPulse config[/]  [dim]{escape(config_path_display())}[/]\n")

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("Key",   style="dim")
    t.add_column("Value", style="bold")

    t.add_row("Downloads dir", str(dl))
    for k, v in cfg.items():
        t.add_row(k, str(v))

    console.print(t)
    console.print()
