# DLPulse CLI

**DLPulse CLI is a lightweight command-line tool for searching, downloading, playing, and Chromecast streaming media via yt-dlp, built for automation, scripting, and headless environments.**

---

## Installation

```bash
git clone https://github.com/calvarr/DLPulse-cli
cd DLPulse/DLPulse_cli

python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Make it a global command (Linux / macOS):**

```bash
chmod +x dlpulse_cli.py
ln -sf "$(pwd)/dlpulse_cli.py" ~/.local/bin/dlpulse
```

---

## Usage

```
python3 dlpulse_cli.py [COMMAND] [OPTIONS]
```

- **No arguments** → launches the TUI (interactive mode)
- **With arguments** → runs the command, prints output, and exits

| Command | What it does |
|---|---|
| `search` | Search YouTube or SoundCloud and print results |
| `download` | Download video or audio from one or more URLs |
| `formats` | List available quality/format presets |
| `play` | Open a file or URL in your media player |
| `cast` | Stream files to a Chromecast over local network |
| `config` | Show current settings and config file path |

Get help for any command:

```bash
python3 dlpulse_cli.py --help
python3 dlpulse_cli.py search --help
python3 dlpulse_cli.py download --help
python3 dlpulse_cli.py cast --help
```

---

## Configuration

Config file is stored at:

- **Linux / macOS:** `~/.config/dlpulse/config.json`
- **Windows:** `%APPDATA%\dlpulse\config.json`

The file is created automatically on first run. You can also copy `config.example.json`:

```bash
mkdir -p ~/.config/dlpulse
cp config.example.json ~/.config/dlpulse/config.json
```

**config.json structure:**

```json
{
  "player_video": "mpv",
  "player_audio": "mpv",
  "chromecast_discovery_seconds": 12,
  "download_dir": ""
}
```

| Key | Description |
|---|---|
| `player_video` | Command to open video files (e.g. `mpv`, `vlc`, `/usr/bin/celluloid`) |
| `player_audio` | Command to open audio files (falls back to `player_video` if empty) |
| `chromecast_discovery_seconds` | How long to scan for Chromecast devices on LAN (1–120 s) |
| `download_dir` | Default download folder. Empty = `~/Downloads` |

**Check current config:**

```bash
python3 dlpulse_cli.py config
```

```
DLPulse config  ~/.config/dlpulse/config.json

  Downloads dir    /home/user/Downloads
  player_video     mpv
  player_audio     mpv
  chromecast_discovery_seconds  12
  download_dir
```

---

## `search` — Search YouTube or SoundCloud

```bash
python3 dlpulse_cli.py search QUERY [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--sc` / `--soundcloud` | off | Search SoundCloud instead of YouTube |
| `-n N` / `--results N` | 15 | Maximum number of results |
| `--download` | off | Download the first result right away |
| `--audio` | off | Audio-only when combined with `--download` |

**Examples:**

```bash
# Search YouTube — prints a numbered table with title + URL
python3 dlpulse_cli.py search "iris goo goo dolls"

# Search with fewer results
python3 dlpulse_cli.py search "beethoven" -n 5

# Search YouTube, download the top result as video
python3 dlpulse_cli.py search "never gonna give you up" --download

# Search YouTube, download the top result as MP3
python3 dlpulse_cli.py search "iris goo goo dolls" --download --audio

# Search SoundCloud
python3 dlpulse_cli.py search "lofi hip hop" --sc

# Search SoundCloud, download the top track as audio
python3 dlpulse_cli.py search "chill beats" --sc --download --audio

# Search SoundCloud, get 30 results
python3 dlpulse_cli.py search "ambient music" --sc -n 30
```

---

## `download` — Download video or audio

```bash
python3 dlpulse_cli.py download URL [URL ...] [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `-f IDX` / `--format IDX` | 0 | Format preset index (see `dlpulse formats`) |
| `--audio` | off | Audio-only MP3 — shortcut for `--format 4` |
| `-o DIR` / `--out DIR` | from config | Destination folder |
| `--no-playlist` | off | If URL is a playlist, download only the specified video |

**Examples:**

```bash
# Download at best quality (default format 0)
python3 dlpulse_cli.py download "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Download as MP3
python3 dlpulse_cli.py download "https://youtube.com/watch?v=dQw4w9WgXcQ" --audio

# Download at 720p (format index 2 — check with: dlpulse formats)
python3 dlpulse_cli.py download "https://youtube.com/watch?v=dQw4w9WgXcQ" --format 2

# Download at 480p
python3 dlpulse_cli.py download "https://youtube.com/watch?v=dQw4w9WgXcQ" --format 3

# Download audio in best original format (no MP3 conversion)
python3 dlpulse_cli.py download "https://youtube.com/watch?v=dQw4w9WgXcQ" --format 5

# Save to a specific folder
python3 dlpulse_cli.py download "https://youtube.com/watch?v=..." --out ~/Music

# Save to Desktop
python3 dlpulse_cli.py download "https://youtube.com/watch?v=..." --out ~/Desktop

# Download multiple URLs in one command
python3 dlpulse_cli.py download URL1 URL2 URL3

# Download multiple URLs as MP3 into a folder
python3 dlpulse_cli.py download URL1 URL2 URL3 --audio --out ~/Music/Songs

# Download a full playlist
python3 dlpulse_cli.py download "https://youtube.com/playlist?list=PLxxxxxx"

# Download a full playlist as MP3
python3 dlpulse_cli.py download "https://youtube.com/playlist?list=PLxxxxxx" --audio

# URL came from a playlist page — download only this single video
python3 dlpulse_cli.py download "https://youtube.com/watch?v=...&list=..." --no-playlist

# Download a SoundCloud track
python3 dlpulse_cli.py download "https://soundcloud.com/artist/track-name"

# Download a SoundCloud playlist
python3 dlpulse_cli.py download "https://soundcloud.com/artist/sets/playlist-name"

# 720p video + custom output folder
python3 dlpulse_cli.py download "https://youtube.com/watch?v=..." \
    --format 2 --out ~/Videos/Movies
```

**Download with a progress bar — output looks like this:**

```
⬇  Downloading: https://youtube.com/watch?v=...
  Downloading · Iris [4K Remaster] ████████████░░░░  73%  0:00:08
  ✓  /home/user/Downloads/a1b2c3/Iris [4K Remaster].mp4
```

---

## `formats` — List format presets

```bash
python3 dlpulse_cli.py formats
```

Shows all available format presets and their index numbers to use with `--format`.

**Typical output:**

```
Available format presets  (use with --format IDX)

 #   Name                      Spec
 0   Video – best quality      bestvideo+bestaudio/best
 1   Video – 1080p             bestvideo[height<=1080]+bestaudio
 2   Video – 720p              bestvideo[height<=720]+bestaudio
 3   Video – 480p              bestvideo[height<=480]+bestaudio
 4   Audio only – MP3          bestaudio/best  [→ mp3]
 5   Audio only – best         bestaudio/best
```

```bash
# List formats
python3 dlpulse_cli.py formats

# Then download with a specific format
python3 dlpulse_cli.py download URL --format 0   # best quality video
python3 dlpulse_cli.py download URL --format 1   # 1080p
python3 dlpulse_cli.py download URL --format 2   # 720p
python3 dlpulse_cli.py download URL --format 4   # MP3 audio
python3 dlpulse_cli.py download URL --format 5   # audio, original format
```

---

## `play` — Play a file or URL

Opens one or more files (or a YouTube/SoundCloud URL) in the player configured in `config.json`. Falls back to `mpv` if no player is configured.

```bash
python3 dlpulse_cli.py play FILE_OR_URL [FILE ...] [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--audio` | off | Use `player_audio` instead of `player_video` |

**Examples:**

```bash
# Play a local video file
python3 dlpulse_cli.py play ~/Downloads/movie.mp4

# Play a local MP3
python3 dlpulse_cli.py play ~/Music/song.mp3

# Force the audio player (uses player_audio from config)
python3 dlpulse_cli.py play ~/Music/song.mp3 --audio

# Play multiple files (passed as a playlist to the player)
python3 dlpulse_cli.py play ep1.mp4 ep2.mp4 ep3.mp4

# Play all MP4 files in a folder (shell glob)
python3 dlpulse_cli.py play ~/Downloads/*.mp4

# Stream a YouTube video directly — no download needed
python3 dlpulse_cli.py play "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Stream audio from SoundCloud
python3 dlpulse_cli.py play "https://soundcloud.com/artist/track" --audio
```

**Player setup in config.json:**

```json
{
  "player_video": "mpv",
  "player_audio": "mpv --no-video"
}
```

Compatible players: `mpv`, `vlc`, `celluloid`, `totem`, `smplayer`, or an absolute path like `/usr/bin/mpv`.
macOS: `iina`, `/Applications/IINA.app/Contents/MacOS/iina-cli`, `vlc`.

---

## `cast` — Stream to Chromecast

Discovers Chromecast devices on your local network (mDNS), starts a local HTTP server to serve the file, and streams it to the selected device.

```bash
python3 dlpulse_cli.py cast FILE [FILE ...] [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `-d NAME` / `--device NAME` | first found | Filter by device friendly name (partial, case-insensitive) |
| `-w SEC` / `--wait SEC` | from config | mDNS scan duration in seconds |

**Examples:**

```bash
# Discover and cast to the first Chromecast found
python3 dlpulse_cli.py cast ~/Downloads/movie.mp4

# Cast to a device whose name contains "living" (case-insensitive)
python3 dlpulse_cli.py cast ~/Downloads/movie.mp4 --device "living"

# Cast to an exact device name
python3 dlpulse_cli.py cast ~/Downloads/movie.mp4 --device "Living Room TV"

# Cast to a Chromecast Audio (speaker)
python3 dlpulse_cli.py cast ~/Music/album.mp3 --device "Kitchen Speaker"

# Cast multiple files in sequence
python3 dlpulse_cli.py cast ep1.mp4 ep2.mp4 ep3.mp4 --device "Bedroom"

# Cast all MP4 files in a folder
python3 dlpulse_cli.py cast ~/Downloads/*.mp4 --device "Living Room"

# Increase discovery timeout on slow Wi-Fi
python3 dlpulse_cli.py cast movie.mp4 --wait 20

# Fast scan (if device is known to respond quickly)
python3 dlpulse_cli.py cast movie.mp4 --device "TV" --wait 5

# Cast an MP4 to the bedroom TV, scan for 8 seconds
python3 dlpulse_cli.py cast ~/Videos/film.mp4 --device "Bedroom" --wait 8
```

**Tip — if your device is not found:**

```bash
# Run with a longer wait to see all devices on your network
python3 dlpulse_cli.py cast dummy.mp4 --wait 20
# Output will list all found devices even if file fails
```

> **Note:** MKV files are not supported by the Chromecast default receiver. Use MP4 (`--format 0`) for best compatibility.

---

## Common Workflows

**Search, pick manually, download:**
```bash
# 1. See the list
python3 dlpulse_cli.py search "pink floyd"

# 2. Copy the URL you want, then download
python3 dlpulse_cli.py download "https://youtube.com/watch?v=..."
```

**One-line: search and grab top result as MP3:**
```bash
python3 dlpulse_cli.py search "comfortably numb" --download --audio
```

**Download a video and immediately cast it:**
```bash
python3 dlpulse_cli.py download "https://youtube.com/watch?v=..." --out /tmp/cast && \
python3 dlpulse_cli.py cast /tmp/cast/*.mp4 --device "Living Room"
```

**Batch download a playlist as MP3s:**
```bash
python3 dlpulse_cli.py download "https://youtube.com/playlist?list=PLxxxxxx" \
    --audio --out ~/Music/Playlist
```

**Download multiple albums in one go:**
```bash
python3 dlpulse_cli.py download \
    "https://youtube.com/playlist?list=ALBUM1" \
    "https://youtube.com/playlist?list=ALBUM2" \
    --audio --out ~/Music
```

**Download at 720p and watch immediately:**
```bash
python3 dlpulse_cli.py download URL --format 2 --out /tmp/watch
python3 dlpulse_cli.py play /tmp/watch/*.mp4
```

**Stream YouTube directly to TV (no download):**
```bash
# mpv can stream YouTube natively
python3 dlpulse_cli.py play "https://youtube.com/watch?v=..."
```

**Check what player is configured:**
```bash
python3 dlpulse_cli.py config
```

---

## Troubleshooting

**`Player not found` error:**
Set `player_video` in config.json to the full path, e.g. `/usr/bin/mpv`, or install mpv:
```bash
# Arch / Manjaro
sudo pacman -S mpv

# Ubuntu / Debian
sudo apt install mpv

# macOS
brew install mpv
```

**Chromecast not found:**
- Make sure your PC and Chromecast are on the same Wi-Fi network.
- Increase `--wait` to 20 seconds or more.
- Check that UDP port 5353 (mDNS) is not blocked by a firewall.

**MKV won't play on Chromecast:**
Download as MP4 instead:
```bash
python3 dlpulse_cli.py download URL --format 0
```

**yt-dlp is outdated (videos fail to download):**
```bash
pip install --upgrade yt-dlp
```

**Best quality / MP3 conversion fails:**
ffmpeg is missing or not in PATH. Install it:
```bash
# Arch / Manjaro
sudo pacman -S ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Verify it works
ffmpeg -version
```

**Check Python version:**
```bash
python3 --version   # must be 3.11 or newer
```

---

## Requirements

### System dependencies — install separately, not via pip

| Tool | Required | Purpose |
|---|---|---|
| **Python 3.11+** | ✅ mandatory | Runtime — specified in `pyproject.toml` |
| **ffmpeg** | ✅ mandatory | Merging video+audio streams, MP3 conversion |
| **mpv** | recommended | Media playback (`play` command) |

**Install on Arch / Manjaro:**
```bash
sudo pacman -S python ffmpeg mpv
```

**Install on Ubuntu / Debian:**
```bash
sudo apt install python3 ffmpeg mpv
```

**Install on macOS (Homebrew):**
```bash
brew install python ffmpeg mpv
```

**Install on Windows:**
- Python: https://python.org/downloads
- ffmpeg: https://ffmpeg.org/download.html (add to PATH)
- mpv: https://mpv.io/installation

> **Why ffmpeg?** yt-dlp downloads video and audio as separate streams at best quality, then uses ffmpeg to merge them into a single file. Without ffmpeg, only pre-merged lower-quality formats are available. ffmpeg is also required for `--audio` (MP3 conversion).

---

### Python packages — install via pip

```bash
pip install -r requirements.txt
```

| Package | Minimum version | Purpose |
|---|---|---|
| `yt-dlp` | 2024.1.1 | Video and audio downloading |
| `rich` | 13.0.0 | Colored output and progress bars |
| `pychromecast` | 14.0.0 | Chromecast discovery and control |

---

## License

Open source. Contributions welcome at [github.com/calvarr/DLPulse](https://github.com/calvarr/DLPulse).

☕ [buymeacoffee.com/medcodex](https://buymeacoffee.com/medcodex)