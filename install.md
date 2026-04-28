# Installing DLPulse CLI

**Project page:** https://github.com/calvarr/DLPulse-cli

---

## Table of Contents

- [Linux](#linux)
  - [Arch / Manjaro](#arch--manjaro)
  - [Ubuntu / Debian](#ubuntu--debian)
  - [Fedora / RHEL](#fedora--rhel)
- [macOS](#macos)
- [Windows](#windows)
- [Install DLPulse CLI](#install-dlpulse-cli)
- [Configuration](#configuration)
- [Verify the installation](#verify-the-installation)
- [Updating](#updating)
- [Uninstalling](#uninstalling)

---

## Linux

### Arch / Manjaro

**1. Python 3.11+**

Arch ships a recent Python by default. Check your version:

```bash
python3 --version
```

If it is older than 3.11:

```bash
sudo pacman -S python
```

**2. ffmpeg**

```bash
sudo pacman -S ffmpeg
```

**3. mpv** *(recommended media player)*

```bash
sudo pacman -S mpv
```

Install everything in one line:

```bash
sudo pacman -S python ffmpeg mpv
```

---

### Ubuntu / Debian

**1. Python 3.11+**

Ubuntu 22.04 ships Python 3.10. Ubuntu 23.04+ and Debian 12+ ship 3.11.

```bash
# Check version
python3 --version

# Ubuntu 22.04 — install 3.11 from deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-pip

# Ubuntu 23.04+ / Debian 12+
sudo apt install python3 python3-venv python3-pip
```

**2. ffmpeg**

```bash
sudo apt install ffmpeg
```

**3. mpv** *(recommended)*

```bash
sudo apt install mpv
```

Install everything in one line (Ubuntu 23.04+ / Debian 12+):

```bash
sudo apt install python3 python3-venv python3-pip ffmpeg mpv
```

---

### Fedora / RHEL

**1. Python 3.11+**

```bash
sudo dnf install python3 python3-pip
```

**2. ffmpeg**

ffmpeg is not in the default Fedora repos. Enable RPM Fusion first:

```bash
sudo dnf install \
  https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
  https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm

sudo dnf install ffmpeg
```

**3. mpv** *(recommended)*

```bash
sudo dnf install mpv
```

---

## macOS

**1. Install Homebrew** *(if not already installed)*

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**2. Python 3.11+**

macOS ships an old Python. Install a current version via Homebrew:

```bash
brew install python
```

Verify:

```bash
python3 --version
```

**3. ffmpeg**

```bash
brew install ffmpeg
```

**4. mpv** *(recommended)*

```bash
brew install mpv
```

Alternatively, install **IINA** (native macOS player):

```bash
brew install --cask iina
```

Install everything in one line:

```bash
brew install python ffmpeg mpv
```

---

## Windows

### Step 1 — Python 3.11+

Download the installer from the official site:

👉 https://www.python.org/downloads/windows/

During installation:

- ☑ **Add Python to PATH** — check this box before clicking Install
- Choose **Install Now**

Verify in PowerShell or Command Prompt:

```powershell
python --version
```

### Step 2 — ffmpeg

**Option A — winget (Windows 10/11 recommended):**

```powershell
winget install ffmpeg
```

**Option B — manual:**

1. Download from https://ffmpeg.org/download.html → Windows → click **Windows builds by BtbN** or **gyan.dev**
2. Extract the ZIP to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system PATH:
   - Search → *Edit the system environment variables* → Environment Variables → Path → New → `C:\ffmpeg\bin`
4. Open a new terminal and verify:

```powershell
ffmpeg -version
```

### Step 3 — mpv *(recommended)*

```powershell
winget install mpv
```

Or download from https://mpv.io/installation/ and add to PATH.

### Step 4 — VLC *(alternative player)*

```powershell
winget install VideoLAN.VLC
```

---

## Install DLPulse CLI

Once Python, ffmpeg, and a media player are ready, install DLPulse CLI on any platform.

### Option A — Clone from GitHub *(recommended)*

```bash
git clone https://github.com/calvarr/DLPulse-cli.git
cd DLPulse-cli
```

Create and activate a virtual environment:

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
python -m venv .venv
.venv\Scripts\activate.bat
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

### Option B — Download ZIP

1. Go to https://github.com/calvarr/DLPulse-cli
2. Click **Code → Download ZIP**
3. Extract the ZIP and open a terminal in the extracted folder
4. Follow the virtual environment steps from Option A

---

### Make it a global command *(optional)*

**Linux / macOS:**

```bash
chmod +x dlpulse_cli.py
ln -sf "$(pwd)/dlpulse_cli.py" ~/.local/bin/dlpulse

# Make sure ~/.local/bin is in your PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

For zsh (macOS default):

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Windows (PowerShell):**

Create a `dlpulse.bat` file in a folder that is already in your PATH (e.g. `C:\Users\YourName\bin`):

```bat
@echo off
C:\path\to\DLPulse-cli\.venv\Scripts\python.exe C:\path\to\DLPulse-cli\dlpulse_cli.py %*
```

---

## Configuration

DLPulse CLI reads its settings from a JSON file:

| Platform | Config file location |
|---|---|
| Linux | `~/.config/dlpulse/config.json` |
| macOS | `~/.config/dlpulse/config.json` |
| Windows | `%APPDATA%\dlpulse\config.json` |

Copy the example config to get started:

```bash
# Linux / macOS
mkdir -p ~/.config/dlpulse
cp config.example.json ~/.config/dlpulse/config.json

# Windows (PowerShell)
mkdir "$env:APPDATA\dlpulse"
Copy-Item config.example.json "$env:APPDATA\dlpulse\config.json"
```

Edit the file and set your player and download folder:

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
| `player_video` | Player for video files — `mpv`, `vlc`, or absolute path |
| `player_audio` | Player for audio files — leave empty to use `player_video` |
| `chromecast_discovery_seconds` | Seconds to scan for Chromecast devices (1–120) |
| `download_dir` | Download folder — leave empty to use `~/Downloads` |

---

## Verify the installation

```bash
# Show help
python3 dlpulse_cli.py --help

# Show current config
python3 dlpulse_cli.py config

# Check ffmpeg is available (used internally by yt-dlp)
ffmpeg -version

# Quick test — search YouTube
python3 dlpulse_cli.py search "test" -n 3

# Quick test — list format presets
python3 dlpulse_cli.py formats
```

If everything prints without errors, DLPulse CLI is ready.

---

## Updating

**Update DLPulse CLI:**

```bash
cd DLPulse-cli
git pull
pip install -r requirements.txt
```

**Update yt-dlp** *(do this regularly — YouTube changes their API often)*:

```bash
pip install --upgrade yt-dlp

# Or with yt-dlp's built-in updater
yt-dlp -U
```

**Update ffmpeg:**

```bash
# Arch / Manjaro
sudo pacman -Syu ffmpeg

# Ubuntu / Debian
sudo apt upgrade ffmpeg

# macOS
brew upgrade ffmpeg

# Windows
winget upgrade ffmpeg
```

---

## Uninstalling

**Remove DLPulse CLI:**

```bash
# Delete the folder
rm -rf DLPulse-cli

# Remove the global symlink (Linux / macOS)
rm ~/.local/bin/dlpulse
```

**Remove the config:**

```bash
# Linux / macOS
rm -rf ~/.config/dlpulse

# Windows (PowerShell)
Remove-Item -Recurse "$env:APPDATA\dlpulse"
```

**Remove Python packages** *(only if you no longer need them)*:

```bash
pip uninstall yt-dlp rich pychromecast
```

---

## Troubleshooting

**`python3: command not found`**
→ Python is not installed or not in PATH. Follow the installation steps for your platform above.

**`ffmpeg: command not found`**
→ ffmpeg is not installed or not in PATH. DLPulse will still download but only at pre-merged quality — best quality and `--audio` (MP3) won't work.

**`ModuleNotFoundError: No module named 'rich'`**
→ The virtual environment is not activated, or `pip install -r requirements.txt` was not run.

```bash
source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

**Downloads fail or give errors**
→ yt-dlp may be outdated. Update it:

```bash
pip install --upgrade yt-dlp
```

**Chromecast not found**
→ Make sure your PC and Chromecast are on the same Wi-Fi network and try a longer scan:

```bash
python3 dlpulse_cli.py cast file.mp4 --wait 20
```

---

☕ Support the project: [buymeacoffee.com/medcodex](https://buymeacoffee.com/medcodex)