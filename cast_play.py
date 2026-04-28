"""
Local playback and Chromecast: discover Cast targets, serve file over HTTP, play URL.
"""
from __future__ import annotations

import os
import shlex
import socket
import subprocess
import tempfile
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MIME_BY_EXT: dict[str, str] = {
    ".mp4": "video/mp4",
    ".m4v": "video/x-m4v",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".webm": "video/webm",
    ".opus": "audio/opus",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
    ".ts": "video/mp2t",
    ".3gp": "video/3gpp",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".wma": "audio/x-ms-wma",
}


def is_media_file(path: str | Path) -> bool:
    """Whether the path suffix is a known video/audio type for play/Cast."""
    return Path(path).suffix.lower() in MIME_BY_EXT


def content_type_for(path: str) -> str:
    ext = Path(path).suffix.lower()
    return MIME_BY_EXT.get(ext, "application/octet-stream")


def get_lan_ipv4() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def play_local_file(path: str) -> tuple[bool, str]:
    """Open the file with the OS default application (video/audio player)."""
    import platform

    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return False, f"Not a file: {path}"
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", path], start_new_session=True)
        else:
            subprocess.Popen(["xdg-open", path], start_new_session=True)
        return True, ""
    except OSError as e:
        return False, str(e)


def write_temp_m3u_playlist(paths: list[str]) -> str:
    """Write an M3U of ``file://`` URIs; caller may delete the path later."""
    resolved = [Path(p).expanduser().resolve() for p in paths]
    for p in resolved:
        if not p.is_file():
            raise OSError(f"Not a file: {p}")
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        suffix=".m3u",
        prefix="dlpulse_playlist_",
        delete=False,
    )
    out_path = tmp.name
    try:
        tmp.write("#EXTM3U\n")
        for p in resolved:
            tmp.write(p.as_uri() + "\n")
        tmp.close()
        return out_path
    except Exception:
        tmp.close()
        try:
            os.unlink(out_path)
        except OSError:
            pass
        raise


def play_local_paths(paths: list[str]) -> tuple[bool, str]:
    """Open one or more media files in the default app (M3U playlist if several)."""
    if not paths:
        return False, "No files."
    if len(paths) == 1:
        return play_local_file(paths[0])
    try:
        pl = write_temp_m3u_playlist(paths)
    except OSError as e:
        return False, str(e)
    return play_local_file(pl)


def _resolve_player_argv(cmd_line: str) -> list[str] | None:
    """First token must be an executable (``PATH`` or absolute). Returns argv without URL."""
    import shutil

    parts = shlex.split((cmd_line or "").strip(), posix=os.name != "nt")
    if not parts:
        return None
    exe = parts[0]
    resolved = exe if os.path.isabs(exe) and os.path.isfile(exe) else shutil.which(exe)
    if not resolved:
        return None
    return [resolved, *parts[1:]]


def stream_url_in_player(
    page_url: str,
    *,
    use_audio_player: bool = False,
    player_video: str = "",
    player_audio: str = "",
) -> tuple[bool, str]:
    """
    Stream a page URL (YouTube, SoundCloud, …).

    If ``player_video`` / ``player_audio`` are set (shell-like command line), that
    executable is used first, with the URL appended. Otherwise: mpv, VLC, IINA,
    ffplay are tried in order (mpv with ``--no-terminal`` and ``--force-window``).
    """
    import platform
    import shutil

    u = (page_url or "").strip()
    if not u:
        return False, "No URL."

    null = subprocess.DEVNULL
    popen_kw = {
        "stdin": null,
        "stdout": null,
        "stderr": null,
        "start_new_session": True,
        "env": os.environ.copy(),
    }

    def _spawn(argv: list[str]) -> bool:
        try:
            subprocess.Popen(argv, **popen_kw)
            return True
        except OSError:
            return False

    chosen = (player_audio if use_audio_player else player_video) or ""
    fallback = (player_video if use_audio_player else player_audio) or ""

    def _try_config_line(line: str, *, required: bool) -> tuple[bool, str]:
        """
        Returns (True, "") if playback started.
        If ``required`` and the executable is missing, returns (False, err).
        If executable exists but ``Popen`` fails, returns (False, "") so caller can fall back.
        """
        s = (line or "").strip()
        if not s:
            return False, ""
        prefix = _resolve_player_argv(s)
        if not prefix:
            if required:
                return False, f"Player not found (PATH or absolute path): {s!r}"
            return False, ""
        if _spawn(prefix + [u]):
            return True, ""
        return False, ""

    ok, err = _try_config_line(chosen, required=bool(chosen.strip()))
    if ok:
        return True, ""
    if err:
        return False, err
    ok, err = _try_config_line(fallback, required=bool(fallback.strip() and not chosen.strip()))
    if ok:
        return True, ""
    if err:
        return False, err

    mpv = shutil.which("mpv")
    if mpv and _spawn(
        [
            mpv,
            "--no-terminal",
            "--force-window=yes",
            u,
        ]
    ):
        return True, ""

    vlc = shutil.which("vlc")
    if vlc and _spawn([vlc, "--play-and-exit", u]):
        return True, ""

    if platform.system() == "Darwin" and _spawn(["open", "-a", "IINA", u]):
        return True, ""

    ff = shutil.which("ffplay")
    if ff and _spawn([ff, "-autoexit", "-loglevel", "error", u]):
        return True, ""

    return (
        False,
        "No suitable player (mpv, vlc, ffplay) in PATH. Set player_video / player_audio "
        "in ~/.config/dlpulse/config.json or install e.g. mpv.",
    )


def cast_paths_queue_to_device(
    cast,
    local_ip: str,
    server: LocalMediaHTTPServer,
    paths: list[str],
) -> tuple[bool, str]:
    """Queue several LAN media URLs on the Cast default receiver (same folder on ``server``)."""
    try:
        from pychromecast.controllers.media import STREAM_TYPE_BUFFERED
    except ImportError as e:
        return False, str(e)

    try:
        cast.wait(timeout=30.0)
        mc = cast.media_controller
        for i, path in enumerate(paths):
            path = os.path.abspath(path)
            bn = os.path.basename(path)
            url = media_url_for_file(local_ip, server, bn)
            ct = content_type_for(path)
            title = os.path.splitext(bn)[0]
            mc.play_media(
                url,
                ct,
                stream_type=STREAM_TYPE_BUFFERED,
                title=title,
                enqueue=(i > 0),
            )
            if i == 0:
                mc.block_until_active(timeout=45.0)
        return True, ""
    except Exception as e:
        return False, str(e)


class LocalMediaHTTPServer:
    """Serve ``directory`` on 0.0.0.0 so Chromecast on the LAN can GET files by name."""

    def __init__(self, directory: str) -> None:
        self._directory = str(Path(directory).resolve())
        served = self._directory

        class _QuietHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=served, **kwargs)

            def log_message(self, _format: str, *_args) -> None:
                return

        self._httpd = ThreadingHTTPServer(("0.0.0.0", 0), _QuietHandler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1])

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def media_url_for_file(local_ip: str, server: LocalMediaHTTPServer, basename: str) -> str:
    safe = urllib.parse.quote(basename, safe="", encoding="utf-8")
    return f"http://{local_ip}:{server.port}/{safe}"


def discover_chromecasts(timeout: float = 12.0) -> tuple[list, object | None]:
    """
    Returns (chromecast_list, browser).

    Keep the browser alive until after ``cast.disconnect()`` / end of playback:
    ``stop_discovery`` tears down Zeroconf and breaks ``cast.wait()`` / reconnect
    with ``AssertionError: Zeroconf instance loop must be running``.
    """
    try:
        import pychromecast
    except ImportError as e:
        raise RuntimeError(
            "Chromecast requires pychromecast. Install with: pip install pychromecast"
        ) from e

    chromecasts, browser = pychromecast.get_chromecasts(timeout=timeout)
    return list(chromecasts), browser


def stop_chromecast_discovery(browser: object | None) -> None:
    if browser is None:
        return
    try:
        from pychromecast import discovery

        discovery.stop_discovery(browser)
    except Exception:
        pass


def cast_file_to_device(cast, media_url: str, content_type: str, *, title: str | None = None) -> tuple[bool, str]:
    """Connect to device, start default media receiver, play ``media_url``."""
    try:
        from pychromecast.controllers.media import STREAM_TYPE_BUFFERED

        cast.wait(timeout=30.0)
        mc = cast.media_controller
        mc.play_media(
            media_url,
            content_type,
            stream_type=STREAM_TYPE_BUFFERED,
            title=title,
        )
        mc.block_until_active(timeout=45.0)
        return True, ""
    except Exception as e:
        return False, str(e)


def stop_cast_session(cast) -> None:
    try:
        cast.media_controller.stop()
    except Exception:
        pass
    try:
        cast.disconnect(timeout=2.0)
    except Exception:
        pass
