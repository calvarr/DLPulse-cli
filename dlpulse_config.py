"""
DLPulse-cli user configuration (~/.config/dlpulse/config.json).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

if os.name == "nt":
    _config_home = Path(
        os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    )
    CONFIG_DIR = _config_home / "dlpulse"
else:
    CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "dlpulse"
CONFIG_PATH = CONFIG_DIR / "config.json"

# Keys must stay stable for user files on disk.
KEY_PLAYER_VIDEO = "player_video"
KEY_PLAYER_AUDIO = "player_audio"
KEY_CAST_DISCOVERY = "chromecast_discovery_seconds"
KEY_DOWNLOAD_DIR = "download_dir"


def default_download_dir() -> str:
    """``~/Downloads`` when it exists or can be created; else current directory."""
    try:
        d = Path.home() / "Downloads"
        d.mkdir(parents=True, exist_ok=True)
        return str(d.resolve(strict=False))
    except OSError:
        return os.getcwd()


def default_config_dict() -> dict:
    return {
        KEY_PLAYER_VIDEO: "",
        KEY_PLAYER_AUDIO: "",
        KEY_CAST_DISCOVERY: 12.0,
        KEY_DOWNLOAD_DIR: "",
    }


def _clamp_cast_timeout(v: float) -> float:
    if v < 1.0:
        return 1.0
    if v > 120.0:
        return 120.0
    return v


def load_config() -> dict:
    """Merge ``config.json`` with defaults. Missing file → defaults only."""
    base = default_config_dict()
    if not CONFIG_PATH.is_file():
        return base
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(raw, dict):
        return base
    out = {**base}
    for k in base:
        if k not in raw:
            continue
        if k == KEY_CAST_DISCOVERY:
            try:
                out[k] = _clamp_cast_timeout(float(raw[k]))
            except (TypeError, ValueError):
                pass
        elif k in (KEY_PLAYER_VIDEO, KEY_PLAYER_AUDIO, KEY_DOWNLOAD_DIR):
            if isinstance(raw[k], str):
                out[k] = raw[k].strip()
    return out


def download_dir_from_config(cfg: dict | None = None) -> str:
    """Resolved default folder for downloads (config path or ``~/Downloads``)."""
    c = cfg if cfg is not None else load_config()
    raw = (c.get(KEY_DOWNLOAD_DIR) or "").strip()
    if raw:
        expanded = os.path.expanduser(raw)
        if expanded:
            return expanded
    return default_download_dir()


def config_path_display() -> str:
    return str(CONFIG_PATH)
