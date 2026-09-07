# Bobine

<p align="center">
  <img alt="Bobine" src="Assets/Images/bobine_banner.svg" width="100%">
</p>

**The open-source, self-hosted alternative to Les Mills Cinema, Wexer, and Screenly Anthias — offline-first gym video playout, digital signage, and scheduled class player for fitness studios.**

Bobine turns any PC, Mac, or low-cost dedicated mini PC into a complete in-club video system: it schedules and plays pre-recorded group-fitness class videos on your screens, lets members browse and start a class on demand from a kiosk, drives a wired and a networked display independently, runs a coach audio mode with animated backgrounds, and streams 24/7 background music. Everything runs locally on your own hardware. No cloud, no subscription, no vendor lock-in, no internet required after setup.

[Official Website](https://bobine.fit) · [Documentation](https://bobine.fit/fr/documentation) · [Français](README.fr.md) · [Technical Architecture](docs/ARCHITECTURE.md) · [Latest Release](https://github.com/FantasmaGlad/Bobine/releases/latest) · [Beta Release](https://github.com/FantasmaGlad/Bobine/releases/tag/beta)

[![CI](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg)](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml)
[![Release: v3.0.0](https://img.shields.io/badge/Release-v3.0.0-brightgreen)](https://github.com/FantasmaGlad/Bobine/releases/latest)
![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue)
![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![Platforms: Windows 11 | Debian | Ubuntu | macOS](https://img.shields.io/badge/Platforms-Windows%2011%20%7C%20Linux%20%7C%20macOS-blue)
![Self-hosted](https://img.shields.io/badge/Self--hosted-Local--first-4c1)

---

## Quick Download & Native Desktop Applications

Install Bobine as a native desktop application on your workstation or studio PC in seconds:

| Platform | Format | Architecture | Direct Download / Command | Experience & Features |
| :--- | :---: | :---: | :---: | :--- |
| ![Windows 11](https://img.shields.io/badge/Windows_11-0078D4?style=flat-square&logo=windows11&logoColor=white) | <sub>`.exe`<br>*(Installer)*</sub> | <sub>x86-64</sub> | <sub>[**Download Bobine-Setup-3.0.0.exe**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/Bobine-Setup-3.0.0.exe)</sub> | **Windows 11, 10 & Windows IoT**<br><sub>• 1-click wizard & Desktop shortcut</sub><br><sub>• Auto-opens browser (`http://127.0.0.1:8000`)</sub><br><sub>• Background tray, zero terminal window</sub> |
| ![Debian](https://img.shields.io/badge/Debian-A81D33?style=flat-square&logo=debian&logoColor=white) ![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=flat-square&logo=ubuntu&logoColor=white) | <sub>`.deb`<br>*(Package)*</sub> | <sub>x86-64<br>*(amd64)*</sub> | <sub>[**Download bobine_3.0.0_amd64.deb**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/bobine_3.0.0_amd64.deb)</sub> | **Debian, Ubuntu & Linux Mint**<br><sub>• Ubuntu App Center / `apt install`</sub><br><sub>• XDG standard Desktop launcher</sub><br><sub>• System notification tray (systray)</sub> |
| ![macOS](https://img.shields.io/badge/macOS-000000?style=flat-square&logo=apple&logoColor=white) | <sub>`.dmg`<br>*(Disk Image)*</sub> | <sub>Apple Silicon<br>*(arm64)*</sub> | <sub>[**Download Bobine-3.0.0.dmg**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/Bobine-3.0.0.dmg)</sub> | **Apple Silicon (M1, M2, M3, M4)**<br><sub>• Drag-and-drop `Bobine.app` into Applications</sub><br><sub>• Native Retina `.icns` icon & menu bar companion</sub><br><sub>• Automatic LaunchAgent autostart at login</sub> |
| ![Android](https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white) | <sub>`.apk`<br>*(Package)*</sub> | <sub>ARM64</sub> | <sub>*Coming soon...*</sub> | **Android Tablets & ARM Touch Kiosks**<br><sub>• Wired USB-C DisplayPort video output (Xiaomi Pad 6/7/8, Galaxy Tab)</sub><br><sub>• Touch coach console & standalone playout (Chaquopy feasibility study)</sub><br><sub>• Active development to expand hardware portability</sub> |
| ![iOS / iPadOS](https://img.shields.io/badge/iOS%20%2F%20iPadOS-000000?style=flat-square&logo=apple&logoColor=white) | <sub>iPadOS App<br>*(Explored Track)*</sub> | <sub>ARM64 (Apple Silicon)</sub> | <sub>*Explored track...*</sub> | **iPads & Apple Touch Tablets**<br><sub>• Wired video over USB-C (DisplayPort) or Thunderbolt (iPad Pro M-series, iPad Air)</sub><br><sub>• Dual-screen coach console & standalone studio video playout</sub><br><sub>• Prospective track to extend touch device portability</sub> |
| ![Bobine Assistant](https://img.shields.io/badge/Bobine_Assistant-FFC131?style=flat-square&logo=tauri&logoColor=black) | <sub>Native Binary<br>*(Tauri 2)*</sub> | <sub>x86-64 (Linux)</sub> | <sub>[**Download bobine-assistant**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/bobine-assistant)</sub> | **Graphical Network Installer (GUI)**<br><sub>• Multi-interface `/24` subnet discovery scan</sub><br><sub>• Remote hardware audit & automated SSH deploy</sub><br><sub>• Zero command-line knowledge needed</sub> |
| ![Bash CLI](https://img.shields.io/badge/Bash_CLI-4EAA25?style=flat-square&logo=gnubash&logoColor=white) | <sub>Shell Script<br>*(Automated)*</sub> | <sub>x86-64</sub> | <sub>`curl -sSL https://bobine.fit/install.sh \| bash`</sub> | **Headless Dedicated Appliance**<br><sub>• 15-step automated install for Debian 13 mini PCs</sub><br><sub>• Hardware 4K VA-API decoding (&lt; 8% CPU)</sub><br><sub>• HDMI-CEC TV control & auto-healing services</sub> |
| [![bobine.fit](https://img.shields.io/badge/bobine.fit-4285F4?style=flat-square&logo=data%3Aimage/svg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0OCA0OCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4Ij48cGF0aCBmaWxsPSIjNENBRjUwIiBkPSJNNDQgMjRjMCAxMS4wNDUtOC45NTUgMjAtMjAgMjAtNC41MiAwLTguNjgtMS41MDMtMTIuMDMtNC4wNDNsOS40NjctMTYuMzk0QTggOCAwIDAgMCAyNCAzMmM0LjQxOCAwIDgtMy41ODIgOC04eiIvPjxwYXRoIGZpbGw9IiNGQkMwMkQiIGQ9Ik00NCAyNEgyNGE4IDggMCAwIDAtNi45MjggNGwtOS40NjcgMTYuMzk0QTE5LjkyIDE5LjkyIDAgMCAxIDQgMjRDNCAxMy45ODcgMTEuMzg1IDUuNzA0IDIxLjAzNiA0LjIyTDMwLjUwMyAyMC42MUE3Ljk3IDcuOTcgMCAwIDAgMzIgMjR6Ii8%2BPHBhdGggZmlsbD0iI0U1MzkzNSIgZD0iTTI0IDRjNy40MDYgMCAxMy44NiA0LjAyNCAxNy4zIDEwLjAyN0wzMC41MDMgMjAuNjFBOCA4IDAgMCAwIDI0IDE2Yy0zLjE1NSAwLTUuOTE0IDEuODI2LTcuMjUgNC40OUw3LjI4NCA0LjA5NUMxMS44OTIgNC4wMzIgMTcuNjUgNCAyNCA0eiIvPjxjaXJjbGUgY3g9IjI0IiBjeT0iMjQiIHI9IjgiIGZpbGw9IiNGRkYiLz48Y2lyY2xlIGN4PSIyNCIgY3k9IjI0IiByPSI2IiBmaWxsPSIjMTk3NkQyIi8%2BPC9zdmc%2B)](https://bobine.fit) | <sub>Web Portal</sub> | <sub>Universal</sub> | <sub>[**Visit bobine.fit**](https://bobine.fit)</sub> | **Official Website & Documentation**<br><sub>• Getting started guides, updates & changelogs</sub><br><sub>• Web app remote and online documentation</sub> |
| ![GitHub](https://img.shields.io/badge/GitHub-Releases-181717?style=flat-square&logo=github&logoColor=white) | <sub>Source & Binaries</sub> | <sub>Multi-OS</sub> | <sub>[**Browse GitHub Releases**](https://github.com/FantasmaGlad/Bobine/releases/latest)</sub> | **Full Release History & Sources**<br><sub>• Checksums, tarballs & complete release notes</sub> |

### Beta Program — Early Access

Want to try upcoming features before they reach the stable release? Bobine ships a **Beta channel**: a single, always-current pre-release build, rebuilt from the latest development code — no need to track version numbers, an equal or newer stable release always supersedes it automatically, and you can switch back to Stable at any time with no data loss.

[**Browse the Beta release**](https://github.com/FantasmaGlad/Bobine/releases/tag/beta) — same platforms as above (`.exe`, `.deb`, `.dmg`, `bobine-assistant`, `install.sh`), file names suffixed `-beta` instead of a version number.

How to opt in permanently, so future updates keep offering Beta builds:
- **Already installed** → Settings → Software Updates → "Bobine Beta Program", switch to Beta.
- **Headless appliance installer** → `sudo ./install.sh --channel=beta`
- **Bobine Assistant (remote install wizard)** → toggle "Bobine Beta Program" in the Options step.

Full details on how the Beta channel works (update detection, downgrade behavior, release process): [Technical Architecture § Canal de mise à jour](docs/ARCHITECTURE.md#7-script-dinstallation--services-systemd).

---

## Why Bobine

Group-fitness rooms increasingly run pre-recorded, instructor-led video classes ("virtual classes") on a big screen. Proprietary solutions like Les Mills Cinema or cloud SaaS platforms like Wexer lock operators into closed platforms, recurring per-screen subscriptions, and external dependencies that stop working when the internet drops. Bobine delivers the same in-club experience — scheduled classes, an on-demand kiosk, a polished member experience — while keeping you in full control:

- **You own it.** Your videos, your hardware, your schedule. No monthly fee, no vendor lock-in, no account.
- **It works offline.** Once installed, the club needs no internet connection to run classes.
- **The source is open.** AGPL-3.0-licensed and auditable — the system's future doesn't depend on a vendor's business decisions.
- **It runs on cheap hardware.** A second-hand thin client or mini PC (Dell Wyse 5070 class) is enough — no recurring licence fee per screen.
- **It is unattended.** Auto-starts on power-up, recovers from power loss, and restarts a failed component on its own.

### Positioning & Alternatives
- **Alternative to proprietary fitness subscriptions (Les Mills Cinema, Wexer Virtual, Fitness On Demand, Radical Fitness / franchise video packages like Yako)**: Bobine removes recurring monthly license fees and catalog constraints. Operators have full freedom over their video content (custom coach recordings or independent libraries), timetables, and studio branding, with 100% offline local SSD reliability.
- **Alternative to generic digital signage (Screenly Anthias, Yodeck, Xibo, TouchPlayer, Waves System)**: Unlike passive billboard or menu loopers, Bobine is purpose-built for fitness operations: automated HDMI-CEC TV power management, interactive member on-demand touch kiosk, smartphone coach remote control via local QR code, and 24/7 background audio with crossfade and automated voice announcements, running smoothly on cost-effective x86-64 mini PCs with VA-API hardware decoding.

Typical users: boutique studios, gyms, hotel and corporate fitness rooms, physiotherapy and rehab spaces, dance and cycling studios — anyone who plays scheduled or on-demand fitness videos on a screen, and anyone looking for a sovereign, self-hosted alternative without the subscription.

Bobine is program-agnostic: class categories are free-form, so it fits any catalogue of group-fitness, cycling, strength, mobility or wellbeing classes.


---

## Features

- **Video scheduling** — build a weekly timetable; classes start automatically at the right time on the right screen.
- **On-demand cinema kiosk** — a member-facing full-screen browser to pick and start a class themselves, with a launch animation and a "up next" countdown.
- **Two independent display outputs** — drive a wired screen (HDMI) and a networked screen separately, each with its own content.
- **Mobile remote** — control playback (play, pause, seek, next) from any phone on the local network.
- **Physical remote support** — the member cinema and the radio screen respond to a plug-and-play USB remote (presenter / media "air remote"): arrow keys and OK to browse and start a class, plus play/pause, track and volume keys. No driver, no pairing — the remote is seen as a keyboard.
- **Coach audio mode** — play audio-only classes over the room speakers with an animated or still visual background on screen.
- **Built-in radio** — a Spotify-style 24/7 background-music player with crossfade, shuffle, repeat, and scheduled spoken reminders ("re-rack your weights", etc.).
- **Simple library management** — drag-and-drop import, bulk upload, free-form categories, grouped selection, per-file import progress, automatic thumbnails.
- **Local-first and resilient** — automatic recovery after a reboot or power cut, and a health watchdog that restarts a dead component.
- **Web admin + zero client install** — administer everything from a browser; member screens and remotes are just web pages.
- **Screen Wake Lock API** — prevents screen sleep automatically during workouts and radio playback across all modern browsers.

---

## How it works

Bobine is a single host machine on your local network running:

- a **FastAPI** backend with **SQLite** for storage;
- a **Chromium** kiosk in full screen (X11) for the wired screen (on headless appliances);
- a **Next.js** admin panel, member kiosk, and mobile remote, all served as static pages from the same machine.

Other screens (networked display, member remotes, the admin PC) are ordinary web browsers pointing at the Bobine host. Media never leaves your network.

For the full architecture, data model, network contract and API reference, see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Supported Hardware

Bobine is lightweight and designed to run smoothly on virtually any standard computer, laptop, or dedicated hardware:

- **Laptops & Desktop PCs (Windows 11 / 10 & Linux)**:
  - Standard consumer and office laptops: **HP Pavilion**, **Acer Aspire Go**, Lenovo IdeaPad/ThinkPad, Dell Inspiron/Latitude, ASUS Vivobook, etc.
  - Any desktop tower or compact PC with 4 GB+ RAM.
- **Apple Mac (macOS)**:
  - **MacBook Air & MacBook Pro** (Apple Silicon M1, M2, M3, M4).
  - **Mac Mini & iMac** (ideal ultra-compact, silent studio video players).
- **Dedicated Mini PCs & Thin Clients (Ideal for 24/7 autonomous gym setups)**:
  - Affordable refurbished units: **Dell Wyse 5070**, **HP ProDesk 400/600 DM**, **Lenovo ThinkCentre Tiny**, **Beelink Mini S12/EQ12**, Intel NUC.
  - Can be run as a regular desktop app or as a 100% headless unattended Linux appliance (Debian 13).
- **Screens & Audio Playout**:
  - Any standard TV, monitor, or projector connected via **HDMI** or **DisplayPort**.
  - Optional secondary screen: any tablet, smart TV, or laptop with a web browser on the local Wi-Fi.
  - Standard 3.5mm jack, HDMI audio, USB soundcard, or Bluetooth speaker for gym sound.

> For advanced technical benchmarks, GPU VA-API hardware decoding details, and appliance systemd architecture, see the dedicated [**Technical Architecture Documentation (docs/ARCHITECTURE.md)**](docs/ARCHITECTURE.md).

---

## Installation & Deployment Options

Bobine offers distinct deployment paths to match your exact setup:

1. **Option 1: Native Graphical Desktop App (Simplest for standard PCs & Laptops)**: Windows 11/10, Linux (Debian/Ubuntu), and macOS (Apple Silicon). Installs like any regular software, auto-opens the web admin upon double-clicking the desktop icon, and lives quietly in your system tray.
2. **Option 2: Dedicated Headless Linux Appliance (Best for autonomous clubs & fine control)**: Turns a bare-metal mini PC (such as a Dell Wyse 5070) into a dedicated, unattended appliance booting directly into a locked full-screen X11 kiosk with automated HDMI-CEC TV power management. Fast 1-line CLI install.
3. **Option 3: Bobine Assistant, Graphical Installer (`assistant/`)**: A cross-platform graphical tool to discover, inspect, and deploy appliances over the local network via SSH.

---

### Option 1 — Native Graphical Desktop App (Windows, Linux & macOS)

#### On Windows (11, 10 or Windows IoT)

1. **Download** [**`Bobine-Setup-3.0.0.exe`**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/Bobine-Setup-3.0.0.exe) (or from the [latest GitHub release](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Run the installer** and follow the wizard (French/English selection, AGPL-3.0 license acceptance).
   - Installs Bobine into `Program Files\Bobine`.
   - Creates a **Desktop** shortcut with the official Bobine icon and adds an entry to the Start Menu.
   - Configures automatic Windows Defender Firewall rules for local network access (mobile remote).
   - Registers silent autostart in the background at user sign-in.
   - *Note*: If Windows SmartScreen displays an "Unrecognized app" alert, click **More info → Run anyway** (Bobine is open-source and free of paid corporate certificates).
3. **Double-click the Bobine Desktop icon**:
   - The backend starts seamlessly in the background with **zero black console window**.
   - Your default browser automatically opens the admin interface at `http://127.0.0.1:8000`.
   - An icon appears in the system tray (notification area next to the clock) to reopen the admin panel, launch the full-screen kiosk display, restart the engine, or quit.
   - If Bobine is already running, clicking the Desktop icon instantly refocuses your browser without conflicting.
4. **Access from other devices**: Open `http://bobine.local` from any tablet, smartphone, or PC connected to the same local Wi-Fi / LAN network. Application data (videos, SQLite database, logs) is securely stored in `%ProgramData%\Bobine`.

#### On Linux Desktop (Debian, Ubuntu, Linux Mint & derivatives)

1. **Download** [**`bobine_3.0.0_amd64.deb`**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/bobine_3.0.0_amd64.deb) (or from the [latest GitHub release](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Install the package** via the Ubuntu App Center / GNOME Software by double-clicking the file, or via the terminal:
   ```bash
   sudo apt install ./bobine_*_amd64.deb
   ```
   *(All runtime dependencies including `ffmpeg` are resolved automatically, and multi-resolution icons are integrated into the system theme).*
3. **Launch Bobine** from your **Desktop** shortcut, the Applications menu, or by typing `bobine` in a terminal.
   - The Bobine tray icon appears in your status bar / system tray.
   - XDG autostart is automatically configured at desktop login.
   - Your media files, database, and settings live cleanly in your user directory following the XDG specification: `~/.local/share/bobine/`.

#### On macOS (Apple Silicon - M1/M2/M3/M4)

1. **Download** [**`Bobine-3.0.0.dmg`**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/Bobine-3.0.0.dmg) (or from the [latest GitHub release](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Open the .dmg** and drag `Bobine.app` into your **Applications** folder.
3. **Launch Bobine** from Applications, your **Desktop** (shortcut created automatically), or Spotlight.
   - *First launch*: Since Bobine is free open-source software without an Apple Developer subscription, Gatekeeper will display a security notice. Open **System Settings → Privacy & Security**, scroll down to the "Bobine was blocked" section, click **Open Anyway**, and confirm.
   - Bobine configures a LaunchAgent so it starts automatically at login. A menu bar icon lets you open the admin dashboard, start the full-screen kiosk, restart the engine, or quit.
4. **Open the interface**: `http://bobine.local` from any device on your local network (or `http://127.0.0.1:8000` locally). Data is stored in `~/Library/Application Support/Bobine`.

---

### Dedicated Servers & Headless Appliances — Advanced Installation Methods

For studios, fitness clubs, and integrators deploying autonomous 24/7 kiosks on dedicated low-cost mini PCs (Dell Wyse 5070, HP ProDesk DM...) without desktop overhead:

| Method | Type | Target Hardware | Deployment Process | Key Features |
| :--- | :---: | :---: | :--- | :--- |
| <img src="Assets/Images/bash.svg" width="20" height="20" valign="middle" alt="Bash"> **Bash Installer (CLI)** | <sub>Shell Script</sub> | <sub>Debian 13 (Mini PC)</sub> | <sub>`curl -sSL https://bobine.fit/install.sh \| bash`</sub> | <sub>• Full 15-step automated sequence</sub><br><sub>• Hardware VA-API 4K decoding (&lt; 8% CPU)</sub><br><sub>• HDMI-CEC TV automation on/off</sub><br><sub>• Locked X11 fullscreen kiosk without screensaver</sub><br><sub>• Auto-healing systemd services</sub> |
| <img src="Assets/Images/network.svg" width="20" height="20" valign="middle" alt="Network"> **Bobine Assistant (Tauri)** | <sub>Desktop App<br>*(Tauri 2)*</sub> | <sub>Windows, macOS & Linux</sub> | <sub>GUI wizard via SSH remote deployment</sub> | <sub>• Multi-interface `/24` subnet network scan</sub><br><sub>• Live hardware audit (CPU, GPU, RAM, storage)</sub><br><sub>• 5-step guided visual orchestrator</sub><br><sub>• Zero command-line knowledge needed</sub> |

#### Option 2 — Dedicated Headless Linux Appliance (Mini PC / Debian 13)

> **For studio operators seeking 100% independence, zero manual intervention, and fine hardware management.**  
> This mode turns a low-cost refurbished mini PC (such as a Dell Wyse 5070, HP ProDesk DM, or Lenovo Tiny) into a dedicated 24/7 video appliance that boots straight into a full-screen hardware-accelerated kiosk without any desktop overhead.

##### 1. Minimal Debian 13 Setup
1. **Download** the Debian 13 "Trixie" *netinst* ISO (~700 MB) from <https://www.debian.org/download>.
2. **Flash it to a USB stick** (8 GB+) using [balenaEtcher](https://etcher.balena.io/) or `dd`.
3. **Install on the mini PC**: In the software selection step, uncheck all desktop environments and keep only **SSH server** and **standard system utilities**.

##### 2. Fast 1-Line CLI Installation
Connect to the mini PC directly or via SSH as your standard non-root user and run:

```bash
# Automated 1-line installation:
curl -sSL https://bobine.fit/install.sh | bash
```

*(Alternatively, for full source control and custom flags: `git clone https://github.com/FantasmaGlad/Bobine.git && cd Bobine && sudo ./install.sh`).*

**What `install.sh` configures automatically:**
- System packages: Python virtualenv, Uvicorn, SQLite, Chromium, FFmpeg with VA-API hardware decoding.
- Full-screen X11 kiosk auto-login with screen saver suppression.
- HDMI-CEC TV automation: automatically turns commercial TV displays on/off according to class schedules.
- Systemd services (`bobine-backend.service`, `bobine-kiosk.service`, `bobine-audio-guard.service`).
- System health watchdog: automatic restart upon unexpected failures and full power-loss recovery.

---

#### Option 3 — Bobine Assistant, Graphical Installer (`assistant/`)

> **Deploy your club appliances remotely from your own computer, without touching a terminal.**

Located in [`assistant/`](assistant/) (available natively for **Windows**, **Linux**, and **macOS**), the **Bobine Assistant** desktop application guides the appliance deployment end to end:

1. **Automated Network Discovery**: Probes every local network interface's `/24` subnet (Wi-Fi, Ethernet, VPN) to detect all reachable Bobine units.
2. **Guided SSH Deployment**: Establishes a secure SSH connection, performs an automated hardware audit (CPU, GPU VA-API, RAM, storage), and runs `install.sh` inside an embedded live terminal emulator with a real-time progress bar.

---

### Open the Interface & Get Started

From any device connected to the same Wi-Fi / Ethernet network:

```
http://bobine.local
```

Bobine advertises itself over **mDNS (Zeroconf/Bonjour)** as `bobine.local`. If your local network does not resolve mDNS, use the local IP address of the machine (`http://<ip-address>:8000` or port 80 on the appliance).

---

## Using Bobine

- **Admin panel** (`http://bobine.local`) — import and organise videos, background loops, audio classes and radio tracks; build playlists and schedules; manage settings, themes and language.
- **Member cinema** — the wired screen shows a browse menu; members start a class themselves. New imports appear on it automatically.
- **Networked screen** — a second, independent output; choose what each screen shows in *Settings → Display output*.
- **Mobile remote** — open `http://bobine.local` on a phone; it adapts to a remote-control layout for staff.
- **Radio** — open the radio screen on a dedicated device to play background music continuously; controlled from the admin *Radio* tab.
- **Screen sync** — *Settings → Sync screens* clears every connected screen's cache and reloads it with the latest assets, and restarts the services.
- **Backup & Restore** — from *Settings → Backup & Restore*, download a full ZIP archive of your SQLite database and configurations, or restore a previous backup directly from the browser.
- **Factory Data Reset** — from *Settings → Danger Zone*, reset application data (SQLite database and media) while keeping the installed software.

---

## Health and monitoring

Bobine exposes a machine-readable health endpoint:

```
GET http://bobine.local/api/health
```

It reports the status of the **SQLite database** and the **Chromium kiosk**, and returns HTTP `200` when healthy or `503` when a critical component is down. An on-device **watchdog** polls it and automatically restarts a failed component (backend or kiosk), so the club recovers without manual intervention. All services also restart automatically after a power cut.

---

## Uninstall

**On Windows**, uninstall like any desktop app: open *Settings → Apps → Installed apps* (or classic *Programs and Features*), find Bobine, and choose Uninstall. This removes the installed program and shortcuts; `%ProgramData%\Bobine` (your videos, database, and logs) is kept so a reinstall recovers your data.

**On Linux (Desktop)**, uninstall via your software manager or terminal:
```bash
sudo apt remove bobine
```
To purge system configuration as well, run `sudo apt purge bobine`. Your personal data under `~/.local/share/bobine/` is preserved.

**On macOS**, quit Bobine from the menu bar icon, drag `Bobine.app` from Applications to the Trash, then delete `~/Library/LaunchAgents/com.bobine.app.plist` to disable autostart. Your personal data under `~/Library/Application Support/Bobine` is preserved.

On the **headless appliance**, use the dedicated management command:
```bash
sudo ./install.sh --uninstall --purge
```
Add `--purge-data` to also remove imported media (irreversible). Shared system packages are kept. See `sudo ./install.sh --help` for all options.

---

## License

Bobine is free software licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** — see [`LICENSE`](LICENSE). If you run a modified version to provide a network service, you must make your modified source available under the same license.

---

## Status and roadmap

Bobine is in active use in production on dedicated hardware and desktop workstations.

To maximize hardware portability and reduce the equipment footprint in fitness studios, the engineering roadmap actively explores porting Bobine to standalone touch tablets capable of wired video playout:
* **Android Tablets with USB-C DisplayPort** (e.g. Xiaomi Pad 6, 7, or 8, Samsung Galaxy Tab S9/S10): Embedding the FastAPI backend locally via Chaquopy and outputting the video feed to the studio display or projector via Android's Presentation API.
* **Apple iPads with Thunderbolt / USB-C Video** (e.g. iPad Pro M1/M2/M4 with Thunderbolt / USB 4, iPad Air M2 with DisplayPort over USB-C): A single cable or powered dock connects the iPad to the projector, dedicating the touch interface to coach controls while driving full video playout to the studio room.

Issues and contributions are welcome on the [GitHub repository](https://github.com/FantasmaGlad/Bobine).

---

<sub>**Keywords:** open-source Les Mills Cinema alternative, Screenly Anthias alternative for gyms, Wexer Virtual alternative, Fitness On Demand open-source alternative, franchise workout video playout (Radical Fitness, Yako, Les Mills Virtual), self-hosted gym digital signage, group fitness class scheduling software, on-demand gym cinema kiosk, virtual coach player, boutique fitness studio video automation, indoor cycling video playout, HDMI-CEC TV power management, x86-64 thin client, Dell Wyse 5070 video player, offline-first media player, local-first fitness system, background music player for gyms, crossfade gym radio, FastAPI, Next.js, Tauri desktop installer, Windows 11 desktop app, macOS Apple Silicon app, Linux Debian Ubuntu .deb package, cross-platform gym video signage, zero subscription gym software.</sub>
