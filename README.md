# Bobine

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="Assets/Images/bobine_banner_dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="Assets/Images/bobine_banner_light.svg">
    <img alt="Bobine" src="Assets/Images/bobine_banner_dark.svg" width="100%">
  </picture>
</p>

**The open-source, self-hosted alternative to Les Mills Cinema, Wexer, and Screenly Anthias — offline-first gym video playout, digital signage, and scheduled class player for fitness studios.**

Bobine turns a low-cost dedicated mini PC into a complete in-club video system: it schedules and plays pre-recorded group-fitness class videos on your screens, lets members browse and start a class on demand from a kiosk, drives a wired and a networked display independently, runs a coach audio mode with animated backgrounds, and streams 24/7 background music. Everything runs locally on your own hardware. No cloud, no subscription, no vendor lock-in, no internet required after setup.

[Official Website](https://bobine.fit) · [Documentation](https://bobine.fit/fr/documentation) · [Français](README.fr.md) · [Technical Architecture](docs/ARCHITECTURE.md) · [Latest Release](https://github.com/FantasmaGlad/Bobine/releases/latest)

[![CI](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg)](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml)
![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue)
![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![Platforms: Windows 10/11 | Linux (.deb) | macOS](https://img.shields.io/badge/Platforms-Windows%2010%2F11%20%7C%20Linux%20(.deb)%20%7C%20macOS-blue)
![Self-hosted](https://img.shields.io/badge/Self--hosted-Local--first-4c1)

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

## See it in action

Full walkthrough — studio admin, scheduling, member kiosk, mobile remote and radio — in the [2.0 release notes](https://github.com/FantasmaGlad/Bobine/releases/latest).

https://github.com/user-attachments/assets/e33196d8-cfd7-449e-ad7f-0929a0361d10

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

---

## How it works

Bobine is a single mini PC on your local network running:

- a **FastAPI** backend with **SQLite** for storage;
- a **Chromium** kiosk in full screen (X11) for the wired screen;
- a **Next.js** admin panel, member kiosk, and mobile remote, all served as static pages from the same machine.

Other screens (networked display, member remotes, the admin PC) are ordinary web browsers pointing at the mini PC. Media never leaves your network.

For the full architecture, data model, network contract and API reference, see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Hardware requirements

- A **mini PC or x86-64 thin client**:
  - **Recommended Intel models**: Dell Wyse 5070 (Intel Celeron J4105 ~$40-50 refurbished), HP ProDesk 400/600 G4/G5 DM, Lenovo ThinkCentre M710q/M720q Tiny, Beelink Mini S12/EQ12 (N100/N5105).
  - **Recommended AMD models**: HP EliteDesk 705 G4/G5 Mini (AMD Ryzen 3/5 Pro ~$60-80 refurbished), Lenovo ThinkCentre M715q/M725q Tiny, HP T630/T730/T740 Thin Client.
  - Any Debian-compatible x86-64 PC with an Intel iGPU (`iHD`/QuickSync driver) or AMD APU/GPU (`mesa-va-drivers`/Radeon) works; VA-API hardware video decoding is automatically detected and configured.
- **4 GB of RAM** minimum (8 GB recommended), SSD from 64 GB to 256 GB depending on your video library size.
- **One or two screens** (HDMI for the wired output; the networked screen is any device with a browser).
- A **local Wi-Fi network** (a router or access point) to reach the other devices — the networked second screen, the mobile remote and the radio player all connect over the local network. It needs **no internet** and keeps working even if your internet connection drops: the LAN alone is enough. Bobine can also run **fully offline with no network at all**, but then only the single wired (HDMI) screen is used.

Internet is only needed once, to install the operating system and the software.

---

## Installation & Quick Start

Bobine now offers two deployment families tailored to your setup:

1. **Native Graphical Desktop App (Recommended for standard PCs)**: Available natively on **Windows** (10, 11), **Linux** (`.deb` Debian/Ubuntu) and **macOS** (`.dmg`, Apple Silicon). Bobine installs as a traditional desktop application with a notification tray icon, supervises the backend engine in the background, and lets you open the admin dashboard or trigger the full-screen kiosk mode with one click.
2. **Dedicated Headless Linux Appliance (Debian 13)**: For fitness clubs running on a dedicated bare mini PC (such as a Dell Wyse 5070) without a desktop environment, booting directly into an automated full-screen X11 kiosk.

---

### Method 1 — Graphical Desktop App (Windows, Linux & macOS)

#### On Windows (10, 11 or Windows IoT)

1. **Download** `Bobine-Setup-*.exe` from the [latest GitHub release](https://github.com/FantasmaGlad/Bobine/releases/latest).
2. **Run the installer** and follow the wizard (French/English selection, AGPL-3.0 license acceptance). It installs Bobine into `Program Files\Bobine`, adds a Start Menu shortcut, registers autostart at user sign-in, and configures a Windows Defender Firewall rule so your mobile remote can connect over the local network.
   - If Windows SmartScreen displays an "unrecognized publisher" alert, click **More info → Run anyway**.
3. **Bobine starts automatically** in the system tray. Click the tray icon to open the admin panel, launch the full-screen kiosk browser window, restart the backend, or quit.
4. **Open the interface**: `http://bobine.local` from any device on your local network (or `http://127.0.0.1:8000` on the PC itself). Application data (videos, SQLite database, logs) is stored in `%ProgramData%\Bobine`.

#### On Linux with a Desktop (Debian, Ubuntu and desktop derivatives)

1. **Download** `bobine_*_amd64.deb` from the [latest GitHub release](https://github.com/FantasmaGlad/Bobine/releases/latest).
2. **Install the package** via your software manager or terminal:
   ```bash
   sudo apt install ./bobine_*_amd64.deb
   ```
   *(All runtime dependencies including ffmpeg are handled automatically by apt).*
3. **Launch Bobine** from your desktop applications menu or type `bobine` in a terminal.
   - The Bobine tray icon appears in your system notification area and supervises the engine.
   - XDG autostart is enabled at desktop login (and a systemd user unit `systemctl --user start bobine` is also available — use one or the other, not both, to avoid running two instances at once).
   - Your media files, database, and logs live cleanly in your user directory following the XDG specification: `~/.local/share/bobine/`.

#### On macOS (Apple Silicon)

1. **Download** `Bobine-*.dmg` from the [latest GitHub release](https://github.com/FantasmaGlad/Bobine/releases/latest).
2. **Open the .dmg** and drag `Bobine.app` into your **Applications** folder.
3. **Launch Bobine** from Applications or Spotlight.
   - Bobine isn't code-signed yet, so Gatekeeper blocks the first launch: open **System Settings → Privacy & Security**, scroll to the "Bobine was blocked" notice, click **Open Anyway**, then confirm.
   - On this first launch, Bobine installs its own LaunchAgent so it keeps starting automatically at login from then on. A menu bar icon lets you open the admin panel, launch the full-screen kiosk window, restart the backend, or quit.
4. **Open the interface**: `http://bobine.local` from any device on your local network. Application data (videos, database, logs) is stored in `~/Library/Application Support/Bobine`.

---

### Method 2 — Dedicated Headless Linux Appliance (Debian 13 on mini PC)

This mode turns a dedicated, headless mini PC into a 100% self-contained appliance locked in kiosk mode.

#### 1. Install Debian 13 from a USB key
Bobine targets **Debian 13 "Trixie"**, minimal install, no desktop environment.

1. **Download** the Debian 13 *netinst* image (~700 MB) from <https://www.debian.org/download>.
2. **Write it to a USB key** (8 GB+) using [balenaEtcher](https://etcher.balena.io/) or `dd`.
3. **Boot the mini PC from USB** and run the installer: uncheck all desktop environments, keep only **SSH server** and **standard system utilities**.

#### 2. Install Bobine via command line
On the mini PC (directly or via SSH), as your normal user (not root):

```bash
# Fast 1-line installation:
curl -sSL https://bobine.fit/install.sh | bash
```

*(Or manual clone: `git clone https://github.com/FantasmaGlad/Bobine.git && cd Bobine && sudo ./install.sh`).*

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

Bobine is in active use in production on dedicated hardware. Planned: a graphical installer assistant (CLI foundations already in place), a dedicated project website and expanded documentation. Issues and contributions are welcome on the [GitHub repository](https://github.com/FantasmaGlad/Bobine).

---

<sub>**Keywords:** open-source Les Mills Cinema alternative, Screenly Anthias alternative for gyms, Wexer Virtual alternative, Fitness On Demand open-source alternative, franchise workout video alternative (Radical Fitness / Yako), self-hosted gym digital signage, group fitness class scheduling software, on-demand gym cinema kiosk, boutique studio virtual classes, indoor cycling video playout, HDMI-CEC TV automation, x86-64 mini PC, offline-first video player, local-first, FastAPI, Next.js, Windows desktop app, macOS desktop app, Linux .deb package, cross-platform video signage.</sub>
