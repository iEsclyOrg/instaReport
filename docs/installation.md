<div align="center">

# 📥 Installation Guide

### InstaReport — Setup Instructions

[← Back to README](../README.md) &nbsp;·&nbsp; [Docs Index](index.md)

</div>

---

## Overview

InstaReport ships as **standalone binaries** for Windows and Linux, and a **Python build** for Android (Termux). No Python installation is required for the standalone binaries.

> ⚠️ **Always download from official channels only.** Beware of fake copies and mirrors.

| Resource | Link |
|----------|------|
| Official Website | <https://iescly.duckdns.org> |
| Official GitHub | <https://github.com/iEsclyOrg/instaReport> |
| Official Telegram | <https://t.me/iescly> |

---

## 🪟 Windows

### Requirements

- Windows 10 or Windows 11.
- No additional dependencies required.

### Installation

1. Download the latest Windows release from [GitHub Releases](https://github.com/iEsclyOrg/instaReport/releases).
2. Locate `InstaReport-Windows-x86-64.exe`.
3. Double-click to run.

### First Run

1. Launch the executable.
2. On first run, the app may check for updates and prepare its local environment automatically.
3. Enter your license key.
4. Done.

---

## 🐧 Linux

### Requirements

- Ubuntu, Kali Linux or Debian (64-bit).
- No Python installation required — Playwright Chromium is bundled.

### Installation

Option A — `.deb` package (Debian/Ubuntu):

```bash
sudo apt install ./InstaReport-Linux-x86_64.deb
instareport
```

Option B — portable AppImage:

```bash
chmod +x InstaReport-Linux-x86_64.AppImage
./InstaReport-Linux-x86_64.AppImage
```

> If FUSE is unavailable, run with `APPIMAGE_EXTRACT_AND_RUN=1 ./InstaReport-Linux-x86_64.AppImage`.

Download both from the [GitLab release](https://gitlab.com/iEsclyDev/InstaReport/-/releases) or [GitHub Releases](https://github.com/iEsclyOrg/InstaReport/releases).

### First Run

1. Install or run the package (above).
2. Launch InstaReport.
3. Enter your license key.
4. Done.

---

## 🤖 Android (Termux)

> The Termux (Python) build is distributed **exclusively through official channels**. It is not available in this public repository.

### Requirements

- Termux installed from F-Droid or the Google Play Store.
- `pkg update` completed.

### Installation

```bash
pkg update
pkg install git python
```

Then obtain the current Python build from the **official Telegram channel** and follow the included quick-start:

```bash
git clone <official-source-url>
cd <source-folder>
pip install -r requirements.txt
python InstaReport.py
```

> Do not install from third-party mirrors — only use links verified via the official Telegram channel.

---

## 💬 Telegram Bot

The cloud-hosted Telegram bot is available at [@instaReportV2Bot](https://t.me/instaReportV2Bot). No installation is required — just open the chat and activate your license.

---

## 🔑 License Activation

1. Purchase a license from the [official pricing page](https://iescly.duckdns.org/pricing).
2. Launch InstaReport.
3. Enter your activation key.
4. The app validates the key online and binds it to your device.

See the [License Guide](../LICENSE_GUIDE.md) for full licensing terms.

---

## Troubleshooting

Having trouble? See the [Troubleshooting Guide](troubleshooting.md) or [FAQ](../FAQ.md). For further help, contact the [official Telegram channel](https://t.me/iescly).

---

<div align="center">

Copyright © 2021 – 2026 iEsclyDev. All rights reserved.

</div>
