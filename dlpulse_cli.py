#!/usr/bin/env python3
"""
DLPulse — interactive CLI.
Download videos, audio (MP3, etc.), playlists, and channel content.
"""
import os
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Prompt
from rich.table import Table

from cast_play import is_media_file, stream_url_in_player
from dlpulse_config import (
    KEY_CAST_DISCOVERY,
    KEY_PLAYER_AUDIO,
    KEY_PLAYER_VIDEO,
    config_path_display,
    download_dir_from_config,
    load_config,
)
from yt_core import (
    FORMAT_PRESETS,
    detect_content_type,
    extract_url_info,
    get_format_preset,
    run_download,
    search_soundcloud,
    search_youtube,
)

console = Console()

SEARCH_MAX_RESULTS = 15


def _url_prefers_audio_player(url: str) -> bool:
    """Heuristic for which configured stream player to prefer (music vs video sites)."""
    u = url.lower()
    return any(
        h in u
        for h in (
            "music.youtube.com",
            "soundcloud.com",
            "bandcamp.com",
            "mixcloud.com",
        )
    )


class QuitApp(Exception):
    """User typed q / quit / exit to leave the program from anywhere."""


def _want_quit(s: str) -> bool:
    t = (s or "").strip().lower()
    return t in ("q", "quit", "exit")


def _prompt_line(prompt: str, default: str = "") -> str:
    """Read one line; ``q`` / ``quit`` / ``exit`` closes the whole application."""
    line = Prompt.ask(prompt, default=default)
    if _want_quit(line):
        raise QuitApp
    return line.strip()


def _wait_enter(prompt: str = "[dim]Press Enter[/dim]", default: str = "") -> None:
    """Wait for acknowledgement; ``q`` / ``quit`` / ``exit`` closes the application."""
    line = Prompt.ask(prompt, default=default)
    if _want_quit(line):
        raise QuitApp


def _prompt_int(prompt: str, lo: int, hi: int, *, default: int | None = None) -> int:
    """Ask for an integer in ``[lo, hi]`` until valid or user quits (via ``_prompt_line``)."""
    ds = "" if default is None else str(default)
    while True:
        raw = _prompt_line(prompt, default=ds)
        if raw == "" and default is not None:
            n = default
        else:
            try:
                n = int(raw)
            except ValueError:
                console.print(f"[yellow]Enter a whole number from {lo} to {hi}.[/yellow]")
                continue
        if lo <= n <= hi:
            return n
        console.print(f"[yellow]Use a number from {lo} to {hi}.[/yellow]")


def _term_clear() -> None:
    """Clear scrollback (where supported) and the visible screen before new UI."""
    if getattr(sys.stdout, "isatty", lambda: False)():
        # \033[3J clears scrollback on xterm/VTE/Konsole; 2J+H erases display + home cursor
        sys.stdout.write("\033[3J\033[2J\033[H")
        sys.stdout.flush()
    console.clear()


def _run_download_with_cli_progress(
    url: str,
    format_spec: str,
    opts_extra: dict,
    output_dir: str,
) -> tuple[bool, list[str], str | None]:
    """
    Clear screen, show DLPulse header + Rich Progress while yt-dlp runs
    (uses ``run_download`` progress_callback).
    """
    _term_clear()
    console.print(
        Panel.fit("[bold cyan]DLPulse[/bold cyan]", border_style="cyan", padding=(0, 3)),
    )
    console.print("[bold]Download[/bold]")
    console.print(
        "[dim]Progress updates here. yt-dlp may print a short line to stderr if it retries formats.[/dim]\n",
    )

    desc_width = max(24, min(100, (console.width or 80) - 28))

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None, complete_style="green", finished_style="green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        expand=True,
        transient=False,
    ) as progress:
        task = progress.add_task("Starting…", total=100.0)

        def on_progress(d: dict) -> None:
            msg = str(d.get("message") or "")
            frac = d.get("fraction")
            title = str(d.get("title") or "").strip()
            fn = str(d.get("filename") or "").strip()
            bits = [escape(msg)]
            if title:
                bits.append(escape(title[:50] + ("…" if len(title) > 50 else "")))
            if fn:
                bits.append(escape(fn))
            description = " · ".join(bits)[: desc_width + 40]

            if isinstance(frac, (int, float)):
                pct = min(100.0, max(0.0, float(frac) * 100.0))
                progress.update(task, completed=pct, description=description)
            else:
                progress.update(task, description=description)

        return run_download(
            url,
            format_spec,
            opts_extra,
            output_dir,
            progress_callback=on_progress,
        )


def _app_frame(action: str, *body) -> None:
    """Clear terminal; show app title and current step only."""
    _term_clear()
    console.print(
        Panel.fit("[bold cyan]DLPulse[/bold cyan]", border_style="cyan", padding=(0, 3)),
    )
    console.print(f"[bold]{action}[/bold]\n")
    for part in body:
        console.print(part)


def _normalize_user_url(s: str) -> str:
    """Add https:// for bare ``soundcloud.com/…`` host-only pastes."""
    t = (s or "").strip()
    if t.startswith(("http://", "https://")):
        return t
    if "soundcloud.com/" in t.lower():
        return "https://" + t.lstrip("/")
    return t


def _is_direct_link(s: str) -> bool:
    """True = paste/download URL; False = treat as keyword search (YouTube / SoundCloud)."""
    t = s.strip().lower()
    if not t:
        return False
    # Any normal URL: yt-dlp supports YouTube, Vimeo, SoundCloud, TikTok, etc.
    if t.startswith(("http://", "https://")):
        return True
    if "soundcloud.com/" in t:
        return True
    # Common YouTube paste shapes without scheme
    if t.startswith("www.") and ("youtube.com" in t or "youtu.be" in t):
        return True
    if t.startswith("youtu.be/"):
        return True
    if t.startswith(
        ("m.youtube.com/", "youtube.com/", "www.youtube.com/", "music.youtube.com/")
    ):
        return True
    return False


def _pick_downloaded_files_for_playback(paths: list[str]) -> list[str]:
    """
    If a single path, return it as a one-element list.
    Otherwise show a table: pick one row number, or type ``all`` / ``*`` to play
    every file (temporary playlist, same as browse multi-select).
    """
    if not paths:
        return []
    if len(paths) == 1:
        return [paths[0]]
    table = Table(title="New files — pick for playback")
    table.add_column("#", style="cyan", width=4)
    table.add_column("File", style="green", overflow="fold")
    for i, p in enumerate(paths, 1):
        table.add_row(str(i), os.path.basename(p))
    _app_frame(
        "Pick file(s)",
        table,
        "\n[dim]Enter a row number, or type[/dim] [bold]all[/bold] [dim](or[/dim] [bold]*[/bold][dim]) for every file — temporary playlist.[/dim]",
    )
    while True:
        line = _prompt_line(
            f"Number (1–{len(paths)}) or all",
            default="1",
        )
        s = line.strip().lower()
        if not s:
            s = "1"
        if s in ("all", "*", "allfiles"):
            return list(paths)
        try:
            j = int(s)
        except ValueError:
            console.print("[yellow]Enter a whole number or type all.[/yellow]")
            continue
        if 1 <= j <= len(paths):
            return [paths[j - 1]]
        console.print(f"[yellow]Use a number from 1 to {len(paths)}, or all.[/yellow]")


def _playback_menu_for_paths(paths: list[str]) -> None:
    """Play locally, Chromecast, or skip for one or more media file paths (temp M3U if several)."""
    from cast_play import play_local_paths

    paths = [os.path.abspath(p) for p in paths if p]
    if not paths:
        return
    preview = "\n".join(f"  · {escape(os.path.basename(p))}" for p in paths[:20])
    if len(paths) > 20:
        preview += f"\n  … [dim]+{len(paths) - 20} more[/dim]"
    _app_frame(
        "Playback",
        f"[dim]{len(paths)} file(s):[/dim]\n{preview}\n\n"
        "[bold]1[/bold]  Play on this computer\n"
        "[bold]2[/bold]  Chromecast\n"
        "[bold]3[/bold]  Skip",
    )
    choice = _prompt_int("Choice", 1, 3, default=3)
    if choice == 1:
        ok_play, err_play = play_local_paths(paths)
        if ok_play:
            msg = "[green]Opened with the default application.[/green]"
            if len(paths) > 1:
                msg += "\n[dim]Playlist: a temporary .m3u was created in your temp directory.[/dim]"
            _app_frame("Playback", msg)
        else:
            _app_frame("Playback", f"[red]{escape(err_play)}[/red]")
        _wait_enter("[dim]Press Enter to continue[/dim]", default="")
    elif choice == 2:
        _chromecast_flow(paths)


def _playback_menu_for_file(selected: str) -> None:
    _playback_menu_for_paths([selected])


def _is_hidden_name(name: str) -> bool:
    return bool(name.startswith("."))


def _is_single_path_segment(name: str) -> bool:
    if not name or name in (".", ".."):
        return False
    return "/" not in name and "\\" not in name and "\x00" not in name


def _valid_new_folder_name(name: str) -> bool:
    return _is_single_path_segment(name) and not name.startswith(".")


def _list_dir_entries(here: Path) -> tuple[Path | None, list[tuple[Path, str, str]]]:
    """
    ``parent`` is the folder above ``here``, or ``None`` if ``here`` is a filesystem root.
    ``entries`` are only items *inside* ``here``: (path, display label, kind) with kind ``dir`` or ``file``.
    Hidden names skipped; files listed are audio/video only; all non-hidden subfolders included.
    """
    here = here.resolve(strict=False)
    parent: Path | None = None
    if here.parent != here:
        parent = here.parent

    try:
        with os.scandir(here) as it:
            names = list(it)
    except OSError as e:
        raise OSError(str(e)) from e

    dirs: list[str] = []
    files: list[str] = []
    for ent in names:
        if _is_hidden_name(ent.name):
            continue
        try:
            if ent.is_dir(follow_symlinks=True):
                dirs.append(ent.name)
            elif ent.is_file(follow_symlinks=False) and is_media_file(ent.path):
                files.append(ent.name)
        except OSError:
            continue

    rows: list[tuple[Path, str, str]] = []
    for name in sorted(dirs, key=str.casefold):
        rows.append((here / name, name + "/", "dir"))
    for name in sorted(files, key=str.casefold):
        rows.append((here / name, name, "file"))
    return parent, rows


def _browse_media_files_only(entries: list[tuple[Path, str, str]]) -> list[tuple[Path, str]]:
    return [(p, lab.rstrip("/")) for p, lab, k in entries if k == "file"]


def _browse_mkdir(cwd: Path) -> tuple[bool, str]:
    _app_frame("New folder", f"[dim]Create inside:[/dim]\n{escape(str(cwd))}\n")
    name = _prompt_line("Folder name")
    if not _valid_new_folder_name(name):
        return False, "Invalid name: one segment, no / or \\, must not start with ."
    target = cwd / name
    if target.exists():
        return False, "That name already exists."
    try:
        target.mkdir()
    except OSError as e:
        return False, str(e)
    return True, f"Created folder {name!r}"


def _browse_rename_pick_file(cwd: Path, files: list[tuple[Path, str]]) -> tuple[bool, str]:
    """Pick from media files only (# matches the small list, not the main folder table)."""
    if not files:
        return False, "No media files in this folder to rename."
    tbl = Table(title="Choose file to rename")
    tbl.add_column("#", style="cyan", width=4)
    tbl.add_column("Name", style="green", overflow="fold")
    for i, (_p, lab) in enumerate(files, 1):
        tbl.add_row(str(i), escape(lab))
    _app_frame("Rename file", tbl, "\n[dim]0 = cancel[/dim]")
    j = _prompt_int("File #", 0, len(files), default=0)
    if j <= 0 or j > len(files):
        return False, "Cancelled."
    path_obj, label = files[j - 1]
    try:
        src = path_obj.resolve(strict=False)
    except OSError as e:
        return False, str(e)
    if not src.is_file():
        return False, "Not a file."
    try:
        if src.parent.resolve() != cwd.resolve():
            return False, "Path is outside the current folder."
    except OSError:
        return False, "Cannot resolve paths."

    _app_frame(
        "Rename file",
        f"[dim]Current name:[/dim] [green]{escape(label)}[/green]\n\n"
        "[dim]New name — basename only (e.g. song.mp3), same folder.[/dim]\n",
    )
    new_name = _prompt_line("New file name")
    if not _is_single_path_segment(new_name):
        return False, "Invalid new name."
    try:
        dest = (cwd / new_name).resolve(strict=False)
    except OSError as e:
        return False, str(e)
    if dest.parent != cwd.resolve():
        return False, "New name must stay in the current folder."
    if dest.exists():
        return False, "A file or folder with that name already exists."
    try:
        src.rename(dest)
    except OSError as e:
        return False, str(e)
    return True, f"Renamed to {new_name!r}"


def _browse_delete_pick_file(cwd: Path, files: list[tuple[Path, str]]) -> tuple[bool, str]:
    if not files:
        return False, "No media files in this folder to delete."
    tbl = Table(title="Choose file to delete")
    tbl.add_column("#", style="cyan", width=4)
    tbl.add_column("Name", style="green", overflow="fold")
    for i, (_p, lab) in enumerate(files, 1):
        tbl.add_row(str(i), escape(lab))
    _app_frame(
        "Delete file",
        tbl,
        "\n[yellow]This cannot be undone.[/yellow]  [dim]0 = cancel[/dim]",
    )
    j = _prompt_int("File #", 0, len(files), default=0)
    if j <= 0 or j > len(files):
        return False, "Cancelled."
    path_obj, label = files[j - 1]
    try:
        target = path_obj.resolve(strict=False)
    except OSError as e:
        return False, str(e)
    if not target.is_file():
        return False, "Not a file."
    try:
        if target.parent.resolve() != cwd.resolve():
            return False, "Path is outside the current folder."
    except OSError:
        return False, "Cannot resolve paths."

    _app_frame(
        "Delete file",
        f"[yellow]Delete permanently:[/yellow]\n[bold]{escape(label)}[/bold]\n",
    )
    confirm = _prompt_line("Type DELETE to confirm", default="")
    if confirm != "DELETE":
        return False, "Cancelled."
    try:
        target.unlink()
    except OSError as e:
        return False, str(e)
    return True, f"Deleted {label!r}"


def _browse_tools_menu(cwd: Path, entries: list[tuple[Path, str, str]]) -> None:
    files = _browse_media_files_only(entries)
    _app_frame(
        "Browse — tools",
        "[bold]1[/bold]  Rename a media file\n"
        "[bold]2[/bold]  Delete a media file\n"
        "[bold]0[/bold]  Back to folder list",
    )
    c = _prompt_int("Choice", 0, 2, default=0)
    if c == 0:
        return
    if c == 1:
        ok, txt = _browse_rename_pick_file(cwd, files)
    elif c == 2:
        ok, txt = _browse_delete_pick_file(cwd, files)
    else:
        _app_frame("Browse — tools", "[yellow]Invalid choice.[/yellow]")
        _wait_enter("[dim]Press Enter[/dim]", default="")
        return
    tag = "green" if ok else "red"
    _app_frame("Browse — tools", f"[{tag}]{escape(txt)}[/{tag}]")
    _wait_enter("[dim]Press Enter[/dim]", default="")


def _browse_parse_multi_indices(
    raw: str, rows: list[tuple[Path, str, str]]
) -> tuple[list[int] | None, str | None]:
    """
    Multi-select: ``all`` / ``*`` / ``allfiles`` = all media file rows; ``1,2,345`` = those rows.

    Returns ``(indices, None)`` with 1-based indices, ``(None, None)`` if not a multi pattern,
    or ``(None, err)`` on invalid input.
    """
    s = raw.strip().lower()
    if s in ("all", "*", "allfiles"):
        idxs = [i for i, (_, _, k) in enumerate(rows, start=1) if k == "file"]
        if not idxs:
            return None, "No media files in this folder."
        return idxs, None
    if "," not in raw:
        return None, None
    parts = [p.strip() for p in raw.split(",")]
    idxs: list[int] = []
    seen: set[int] = set()
    for p in parts:
        if not p:
            continue
        try:
            n = int(p)
        except ValueError:
            return None, f"Not a valid row number: {p!r}"
        if n < 1 or n > len(rows):
            return None, f"Row out of range: {n}"
        if n not in seen:
            seen.add(n)
            idxs.append(n)
    if not idxs:
        return None, "No row numbers after commas."
    return idxs, None


def _browse_paths_for_indices(
    rows: list[tuple[Path, str, str]], idxs: list[int]
) -> tuple[list[str], str | None]:
    out: list[str] = []
    for n in idxs:
        path_obj, _label, kind = rows[n - 1]
        if kind != "file":
            return [], f"Row {n} is not a media file (use only file rows)."
        try:
            pr = path_obj.resolve(strict=False)
        except OSError as e:
            return [], str(e)
        if not pr.is_file() or not is_media_file(pr):
            return [], f"Row {n} is not a playable media file."
        out.append(str(pr))
    return out, None


def _browse_files_loop() -> None:
    """Navigate the filesystem from home; open media with play or Chromecast."""
    try:
        cwd = Path.home().resolve(strict=False)
    except OSError:
        cwd = Path.cwd().resolve(strict=False)

    help_panel = Panel(
        "[bold]Row number[/bold]  Open that [blue]folder[/blue], or open the play / Chromecast menu for that [green]media[/green] file.\n"
        "[bold]Playlist[/bold]  Comma-separated rows, e.g. [cyan]1,3,5[/cyan] — or [cyan]all[/cyan] / [cyan]*[/cyan] for every media file listed below.\n"
        "[bold]Go up[/bold]  [cyan]up[/cyan]  [cyan]..[/cyan]  [cyan]0[/cyan]  [cyan]back[/cyan]  (parent folder — not a row number)\n"
        "[bold]New folder[/bold]  [cyan]+[/cyan]  or  [cyan]mkdir[/cyan]\n"
        "[bold]Rename / delete[/bold]  [cyan]r[/cyan]  [cyan]d[/cyan]  or  [cyan]t[/cyan] for a small tools menu\n"
        "[bold]Main menu[/bold]  [cyan]m[/cyan]  ·  [bold]Quit program[/bold]  [cyan]q[/cyan]  (works in any prompt)",
        title="How to use this screen",
        border_style="dim",
    )

    while True:
        try:
            cwd = cwd.resolve(strict=False)
        except OSError:
            _app_frame(
                "Browse your files",
                "[red]Current path is invalid. Resetting to home.[/red]",
            )
            try:
                cwd = Path.home().resolve(strict=False)
            except OSError:
                cwd = Path.cwd().resolve(strict=False)
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue

        try:
            parent, entries = _list_dir_entries(cwd)
        except OSError as e:
            _app_frame(
                "Browse your files",
                f"[red]Cannot read folder: {escape(str(e))}[/red]",
            )
            if cwd.parent != cwd:
                cwd = cwd.parent
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue

        table = Table(title="Folders and media in this location")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Kind", style="dim", width=8)
        table.add_column("Name", overflow="fold")
        for i, (_p, label, kind) in enumerate(entries, 1):
            if kind == "dir":
                table.add_row(str(i), "folder", f"[blue]{escape(label)}[/blue]")
            else:
                table.add_row(str(i), "media", f"[green]{escape(label)}[/green]")

        path_show = str(cwd)
        maxw = (console.width or 80) - 8
        if len(path_show) > maxw:
            path_show = "…" + path_show[-maxw + 1 :]

        up_hint = ""
        if parent is not None:
            up_hint = "[dim]Parent:[/dim] use [cyan]up[/cyan], [cyan]..[/cyan], [cyan]0[/cyan], or [cyan]back[/cyan] — not mixed with row numbers.\n\n"

        empty_note = ""
        if not entries:
            empty_note = "[yellow]This folder is empty[/yellow] (no subfolders and no media files). You can still go [cyan]up[/cyan] or create [cyan]+[/cyan] a folder.\n\n"

        _app_frame(
            "Browse your files",
            up_hint + empty_note + f"[dim]Location[/dim]\n[bold]{escape(path_show)}[/bold]\n",
            help_panel,
            table,
        )
        raw = _prompt_line("[bold]Your input[/bold]", default="")
        raw_l = raw.lower()
        if raw_l in ("m", "menu", "b"):
            return
        if not raw:
            continue
        if raw_l in ("n", "mkdir", "md", "+"):
            ok, txt = _browse_mkdir(cwd)
            tag = "green" if ok else "red"
            _app_frame("Browse your files", f"[{tag}]{escape(txt)}[/{tag}]")
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue
        if raw_l in ("t", "tools", "tool"):
            _browse_tools_menu(cwd, entries)
            continue
        if raw_l in ("r", "ren", "rename"):
            ok, txt = _browse_rename_pick_file(cwd, _browse_media_files_only(entries))
            tag = "green" if ok else "red"
            _app_frame("Browse your files", f"[{tag}]{escape(txt)}[/{tag}]")
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue
        if raw_l in ("d", "del", "delete", "rm"):
            ok, txt = _browse_delete_pick_file(cwd, _browse_media_files_only(entries))
            tag = "green" if ok else "red"
            _app_frame("Browse your files", f"[{tag}]{escape(txt)}[/{tag}]")
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue
        if raw_l in ("0", "u", "up", "..", "back", "^"):
            if parent is not None:
                cwd = parent
            continue

        multi_idx, multi_err = _browse_parse_multi_indices(raw, entries)
        if multi_err:
            _app_frame("Browse your files", f"[red]{escape(multi_err)}[/red]")
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue
        if multi_idx is not None:
            media_paths, perr = _browse_paths_for_indices(entries, multi_idx)
            if perr:
                _app_frame("Browse your files", f"[red]{escape(perr)}[/red]")
                _wait_enter("[dim]Press Enter[/dim]", default="")
                continue
            _playback_menu_for_paths(media_paths)
            continue

        try:
            idx = int(raw.strip())
        except ValueError:
            _app_frame(
                "Browse your files",
                f"[yellow]Not recognized:[/yellow] {escape(raw)}\n\n"
                "[dim]Use a row number, [cyan]up[/cyan] / [cyan]all[/cyan], commas like [cyan]1,2[/cyan], or a command from the help box above.[/dim]",
            )
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue
        if idx < 1 or idx > len(entries):
            _app_frame(
                "Browse your files",
                f"[yellow]Row {idx} is out of range.[/yellow]  [dim]This screen lists rows 1–{len(entries)}.[/dim]",
            )
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue

        path_obj, _label, kind = entries[idx - 1]
        try:
            path_resolved = path_obj.resolve(strict=False)
        except OSError:
            _app_frame("Browse your files", "[red]Cannot open that entry.[/red]")
            _wait_enter("[dim]Press Enter[/dim]", default="")
            continue

        if kind == "dir" or path_resolved.is_dir():
            cwd = path_resolved
            continue

        if path_resolved.is_file():
            if is_media_file(path_resolved):
                _playback_menu_for_file(str(path_resolved))
            else:
                _app_frame(
                    "Browse your files",
                    "[yellow]That row is not a supported media type for play / cast.[/yellow]",
                )
                _wait_enter("[dim]Press Enter[/dim]", default="")
            continue

        _app_frame(
            "Browse your files",
            "[yellow]Not a normal file or folder.[/yellow]",
        )
        _wait_enter("[dim]Press Enter[/dim]", default="")


def _cast_resolve_device_pick(raw: str, num_casts: int) -> tuple[list[int] | None, str | None]:
    """
    Parse Cast device selection: one number, comma list (1,2,5), or all / * / alldevices.

    Returns ``(indices_1_based, None)`` on success, ``(None, None)`` if user cancels,
    ``(None, err_message)`` on invalid input.
    """
    s0 = raw.strip()
    if not s0 or s0.lower() in ("0", "cancel"):
        return None, None
    s = s0.lower()
    if s in ("all", "*", "alldevices"):
        if num_casts < 1:
            return None, "No devices in the list."
        return list(range(1, num_casts + 1)), None
    if "," in s0:
        parts = [p.strip() for p in s0.split(",")]
        idxs: list[int] = []
        seen: set[int] = set()
        for p in parts:
            if not p:
                continue
            try:
                n = int(p)
            except ValueError:
                return None, f"Not a valid device number: {p!r}"
            if n < 1 or n > num_casts:
                return None, f"Device number out of range: {n} (use 1–{num_casts})"
            if n not in seen:
                seen.add(n)
                idxs.append(n)
        if not idxs:
            return None, "No device numbers after commas."
        return idxs, None
    try:
        n = int(s0)
    except ValueError:
        return None, f"Unrecognized: {raw.strip()!r}. Use a number, commas like 1,2, or all."
    if n == 0:
        return None, None
    if n < 1 or n > num_casts:
        return None, f"Device number out of range: {n} (use 1–{num_casts})"
    return [n], None


def _chromecast_flow(paths: list[str]) -> None:
    from cast_play import (
        LocalMediaHTTPServer,
        cast_file_to_device,
        cast_paths_queue_to_device,
        content_type_for,
        discover_chromecasts,
        get_lan_ipv4,
        media_url_for_file,
        stop_cast_session,
        stop_chromecast_discovery,
    )

    if not paths:
        return
    paths = [os.path.abspath(p) for p in paths]
    for p in paths:
        if not os.path.isfile(p):
            _app_frame("Chromecast", f"[red]Not a file: {escape(p)}[/red]")
            _wait_enter("[dim]Press Enter to continue[/dim]", default="")
            return
    parents = {str(Path(p).parent.resolve()) for p in paths}
    if len(parents) != 1:
        _app_frame(
            "Chromecast",
            "[red]All selected files must be in the same folder for Chromecast.[/red]",
        )
        _wait_enter("[dim]Press Enter to continue[/dim]", default="")
        return

    # CastBrowser's Zeroconf must stay running until after cast.disconnect();
    # stopping discovery early breaks cast.wait() with "Zeroconf instance loop must be running".
    browser = None
    try:
        cast_timeout = float(load_config().get(KEY_CAST_DISCOVERY, 12.0))
        _app_frame(
            "Chromecast",
            f"[dim]Scanning the local network for Cast devices ({cast_timeout:g}s)…[/dim]",
        )
        try:
            casts, browser = discover_chromecasts(timeout=cast_timeout)
        except RuntimeError as e:
            _app_frame("Chromecast", f"[red]{e}[/red]")
            _wait_enter("[dim]Press Enter to continue[/dim]", default="")
            return

        if not casts:
            _app_frame(
                "Chromecast",
                "[red]No Cast devices found. Check Wi-Fi and that TVs/speakers are on.[/red]",
            )
            _wait_enter("[dim]Press Enter to continue[/dim]", default="")
            return

        table = Table(title="Cast devices")
        table.add_column("#", style="cyan", width=4)
        table.add_column("Name", style="green")
        table.add_column("Type", style="dim")
        for i, c in enumerate(casts, 1):
            info = getattr(c, "cast_info", None)
            name = getattr(info, "friendly_name", None) or f"device-{i}"
            model = getattr(info, "model_name", "") or ""
            ctype = getattr(info, "cast_type", "") or ""
            table.add_row(str(i), name, f"{model} ({ctype})".strip())
        pick_help = (
            "[dim]One device: type its [cyan]#[/cyan].  Several: [cyan]1,3,5[/cyan].  "
            "Every device: [cyan]all[/cyan] or [cyan]*[/cyan].  [cyan]0[/cyan] = cancel.  [cyan]q[/cyan] = quit app.[/dim]"
        )
        _app_frame("Chromecast", table, "\n", pick_help)
        raw_pick = _prompt_line("[bold]Device(s)[/bold]", default="")
        dev_indices, pick_err = _cast_resolve_device_pick(raw_pick, len(casts))
        if pick_err:
            _app_frame("Chromecast", f"[red]{escape(pick_err)}[/red]")
            _wait_enter("[dim]Press Enter to continue[/dim]", default="")
            return
        if dev_indices is None:
            return

        chosen_casts = [casts[i - 1] for i in dev_indices]

        ip = get_lan_ipv4()
        if not ip:
            _app_frame(
                "Chromecast",
                "[red]Could not detect this PC's LAN address. Connect to Wi-Fi/Ethernet.[/red]",
            )
            _wait_enter("[dim]Press Enter to continue[/dim]", default="")
            return

        serve_dir = parents.pop()
        server = None
        try:
            server = LocalMediaHTTPServer(serve_dir)
            server.start()
            time.sleep(0.2)
            errors: list[str] = []
            if len(paths) == 1:
                selected_path = paths[0]
                basename = os.path.basename(selected_path)
                media_url = media_url_for_file(ip, server, basename)
                ct = content_type_for(selected_path)
                title = os.path.splitext(basename)[0]
                _app_frame(
                    "Chromecast",
                    f"[dim]HTTP[/dim] {media_url}\n\n"
                    f"[yellow]Sending to {len(chosen_casts)} device(s)…[/yellow]",
                )
                for idx_1, cast in zip(dev_indices, chosen_casts):
                    info = getattr(cast, "cast_info", None)
                    dname = getattr(info, "friendly_name", None) or f"device-{idx_1}"
                    ok_cast, err_msg = cast_file_to_device(cast, media_url, ct, title=title)
                    if not ok_cast:
                        errors.append(f"{dname}: {err_msg}")
            else:
                _app_frame(
                    "Chromecast",
                    f"[dim]HTTP[/dim] http://{ip}:{server.port}/\n"
                    f"[yellow]Queueing {len(paths)} tracks on each of {len(chosen_casts)} device(s)…[/yellow]",
                )
                for idx_1, cast in zip(dev_indices, chosen_casts):
                    info = getattr(cast, "cast_info", None)
                    dname = getattr(info, "friendly_name", None) or f"device-{idx_1}"
                    ok_cast, err_msg = cast_paths_queue_to_device(cast, ip, server, paths)
                    if not ok_cast:
                        errors.append(f"{dname}: {err_msg}")

            ok_count = len(chosen_casts) - len(errors)
            if errors:
                body = (
                    f"[yellow]Playback started on {ok_count} of {len(chosen_casts)} device(s).[/yellow]\n\n"
                    + "\n".join(escape(e) for e in errors)
                )
                if ok_count == 0:
                    body = "[red]Could not start playback on any device.[/red]\n\n" + "\n".join(
                        escape(e) for e in errors
                    )
                _app_frame("Chromecast", body)
                _wait_enter("[dim]Press Enter to continue[/dim]", default="")
                return
            plural = "s" if len(chosen_casts) != 1 else ""
            _app_frame(
                "Chromecast",
                f"[green]Playback started on {len(chosen_casts)} device{plural}.[/green]\n\n"
                "[dim]Stopping the local server ends the stream for all of them. "
                "Firewall must allow inbound TCP on the printed port from each Cast device.[/dim]",
            )
            _wait_enter("[dim]Press Enter to stop serving and disconnect all[/dim]", default="")
        finally:
            if server is not None:
                server.stop()
            for cast in chosen_casts:
                stop_cast_session(cast)
    finally:
        stop_chromecast_discovery(browser)


def _post_download_playback(new_files: list[str], output_dir: str) -> None:
    """After a successful download: optional local play or Chromecast."""
    paths = [os.path.join(output_dir, f) for f in new_files]
    paths = [p for p in paths if os.path.isfile(p)]
    if not paths:
        return
    picked = _pick_downloaded_files_for_playback(paths)
    if picked:
        _playback_menu_for_paths(picked)


def _resolve_url_or_search(raw: str) -> str | None:
    """
    If raw is a direct page URL, return it (normalized).
    Otherwise pick YouTube vs SoundCloud search, then pick a result URL or None.
    """
    raw = _normalize_user_url(raw.strip())
    if _is_direct_link(raw):
        return raw

    _app_frame(
        "Search",
        f"[dim]Keywords:[/dim] {raw!r}\n\n"
        "[bold]1[/bold]  Search YouTube\n"
        "[bold]2[/bold]  Search SoundCloud\n"
        "[bold]0[/bold]  Cancel",
    )
    src = _prompt_int("Where to search", 0, 2, default=1)
    if src == 0:
        return None
    site = "YouTube" if src == 1 else "SoundCloud"
    hits = (
        search_youtube(raw, max_results=SEARCH_MAX_RESULTS)
        if src == 1
        else search_soundcloud(raw, max_results=SEARCH_MAX_RESULTS)
    )
    if not hits:
        _app_frame(
            f"Search {site}",
            "[red]No results. Try other words or paste a full track / playlist URL.[/red]",
        )
        _wait_enter("[dim]Press Enter to continue[/dim]", default="")
        return None

    table = Table(title="Results")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Title", style="green", overflow="fold")
    for i, h in enumerate(hits, 1):
        table.add_row(str(i), h.get("title") or "Untitled")

    _app_frame(f"Pick a track ({site})", table)
    pick = _prompt_int(
        f"Number (1–{len(hits)}, 0 = cancel)",
        0,
        len(hits),
        default=1,
    )
    if pick == 0:
        return None
    return str(hits[pick - 1]["url"])


def _stream_or_download_menu() -> str | None:
    """Return ``'stream'``, ``'download'``, or ``None`` if the user cancels."""
    _app_frame(
        "Stream or download",
        "[bold]1[/bold]  Stream in player (mpv, VLC) — no file saved\n"
        "[bold]2[/bold]  Download with a chosen format\n"
        "[bold]0[/bold]  Cancel",
    )
    c = _prompt_int("Choice", 0, 2, default=2)
    if c == 0:
        return None
    if c == 1:
        return "stream"
    return "download"


def _download_interactive_loop() -> None:
    """Search / URL, download, optional playback; returns to main menu when user declines another."""
    welcome = Panel.fit(
        "Paste a page [bold]URL[/bold]: YouTube plus many other sites (Vimeo, SoundCloud, …)\n"
        "via the same engine as [dim]yt-dlp[/dim]. Short YouTube links without [dim]https[/dim] work too.\n"
        "Or type [bold]keywords[/bold]: you will choose [bold]YouTube[/bold] or [bold]SoundCloud[/bold] search, then pick a track.\n"
        "After that, choose to [bold]stream[/bold] in a local player (mpv/VLC) or [bold]download[/bold] to disk.\n"
        f"[dim]Optional config:[/dim] [cyan]{escape(config_path_display())}[/cyan]\n"
        "[dim](players, Chromecast scan time, default download folder — see config.example.json in the app folder.)[/dim]\n\n"
        "[dim]Type q, quit, or exit anywhere to close the program.[/dim]",
        title="Download",
        border_style="cyan",
    )
    first = True

    while True:
        hint = welcome if first else "[dim]URL, keywords, or q to quit the program.[/dim]"
        first = False
        _app_frame("URL or search", hint)
        raw = _prompt_line("[bold]Input[/bold]")
        if not raw:
            continue

        url = _resolve_url_or_search(raw)
        if not url:
            continue

        mode = _stream_or_download_menu()
        if not mode:
            continue

        if mode == "stream":
            _app_frame("Stream", "[dim]Opening in external player…[/dim]")
            cfg = load_config()
            ok_stream, serr = stream_url_in_player(
                url,
                use_audio_player=_url_prefers_audio_player(url),
                player_video=str(cfg.get(KEY_PLAYER_VIDEO) or ""),
                player_audio=str(cfg.get(KEY_PLAYER_AUDIO) or ""),
            )
            if ok_stream:
                _app_frame("Stream", "[green]Playback started.[/green]")
            else:
                _app_frame("Stream", f"[red]{escape(serr)}[/red]")
            _wait_enter("[dim]Press Enter to continue[/dim]", default="")
            _app_frame(
                "Stream",
                "[dim]Another URL or search?[/dim] [bold]y[/bold] = yes · [bold]n[/bold] = main menu",
            )
            again = _prompt_line("Answer", default="y").lower()
            if again in ("n", "no", "nu"):
                return
            continue

        _app_frame("Resolving", "[dim]Fetching media info…[/dim]")
        info = extract_url_info(url)
        if not info:
            _app_frame("Error", "[red]Could not access the URL.[/red]")
            _wait_enter("[dim]Press Enter to continue[/dim]", default="")
            continue

        description = detect_content_type(info)[1]
        fmt_table = Table(title="Options")
        fmt_table.add_column("#", style="cyan", width=4)
        fmt_table.add_column("Format", style="green")
        for i, (label, _, _) in enumerate(FORMAT_PRESETS, 1):
            fmt_table.add_row(str(i), label)

        _app_frame(
            "Choose format",
            Panel(f"[green]{description}[/green]", title="Detected", border_style="green"),
            fmt_table,
        )
        idx = _prompt_int("Option number", 1, len(FORMAT_PRESETS), default=1)
        if idx < 1 or idx > len(FORMAT_PRESETS):
            idx = 1
        preset = get_format_preset(idx - 1)
        if not preset:
            continue
        format_spec, opts_extra = preset
        preset_label = FORMAT_PRESETS[idx - 1][0]

        default_out = download_dir_from_config()
        _app_frame(
            "Download folder",
            f"[dim]Format:[/dim] {preset_label}\n"
            f"[dim]Default path (from config or ~/Downloads):[/dim] {escape(default_out)}",
        )
        od = _prompt_line(
            "Path (Enter = use default above)",
            default=default_out,
        )
        output_dir = (od or "").strip() or default_out

        ok, new_files, err = _run_download_with_cli_progress(
            url, format_spec, opts_extra, output_dir
        )
        lines = []
        if err:
            lines.append(f"[red]{err}[/red]")
        if ok:
            lines.append("[green]Download finished.[/green]")
        else:
            lines.append("[red]Download failed.[/red]")
        summary = "\n".join(lines)

        if ok and new_files:
            _app_frame("Done", summary)
            _post_download_playback(new_files, output_dir)
            _app_frame(
                "Download",
                summary,
                "\n[dim]Another URL or search?[/dim] [bold]y[/bold] = yes · [bold]n[/bold] = main menu",
            )
        else:
            _app_frame(
                "Done",
                summary,
                "\n[dim]Another URL or search?[/dim] [bold]y[/bold] = yes · [bold]n[/bold] = main menu",
            )
        again = _prompt_line("Answer", default="y").lower()
        if again in ("n", "no", "nu"):
            return


def main() -> None:
    # ── Dacă există argumente CLI → execută comanda non-interactiv și iese ──
    try:
        from dlpulse_args import run_cli
        if run_cli():
            return
    except ImportError:
        pass  # dlpulse_args.py absent → ignoră, pornește TUI

    # ── Fără argumente → TUI interactiv ──────────────────────────────────────
    try:
        _main_loop()
    except QuitApp:
        _app_frame("Goodbye", "[dim]Thanks for using DLPulse.[/dim]")


def _main_loop() -> None:
    while True:
        main_menu = Panel.fit(
            "[bold]What do you want to do?[/bold]\n\n"
            "[bold]1[/bold]  Search or paste a URL — stream (mpv/VLC) or download (YouTube and other sites)\n"
            "[bold]2[/bold]  Browse your files (folders + media), then play locally or Chromecast\n"
            "[bold]0[/bold]  Exit\n\n"
            f"[dim]Config file:[/dim] [cyan]{escape(config_path_display())}[/cyan]\n"
            "[dim]Tip: type [cyan]q[/cyan] at almost any prompt to exit the program.[/dim]",
            title="DLPulse",
            border_style="cyan",
        )
        _app_frame("Start", main_menu)
        choice = _prompt_int("Choice", 0, 2, default=1)
        if choice == 0:
            _app_frame("Goodbye", "[dim]Thanks for using DLPulse.[/dim]")
            break
        if choice == 1:
            _download_interactive_loop()
        elif choice == 2:
            _browse_files_loop()
        else:
            _app_frame("Start", "[yellow]Choose 0 (exit), 1 (download), or 2 (browse).[/yellow]")
            _wait_enter("[dim]Press Enter[/dim]", default="")


if __name__ == "__main__":
    main()