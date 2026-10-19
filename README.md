# Bobine

<p align="center">
  <img alt="Bobine" src="Assets/Images/LogoBanniere.png" width="100%">
</p>

<table align="center">
  <tr>
    <td align="center" valign="middle"><img alt="Google Book compatible avec Bobine" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/googlebooks.webp" width="400"></td>
    <td align="center" valign="middle"><img alt="Bobine supports Firefox — the Firefox fox and Baamix, Bobine's mascot" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/FirefoxBaamix.png" width="400"></td>
  </tr>
</table>

<p align="center">
  <b>Recently added — Bobine now officially supports Firefox & ARM64 Architecture.</b><br>
  <sub>Native ARM64 ecosystem (Snapdragon X laptops, Linux ARM64, NVIDIA DGX Spark, Google Books), three-tier update system (Stable/Beta/Canary), and Firefox 157 verification. <a href="#supported-browsers">Browser support</a></sub>
</p>

<p align="center">
  <a href="https://bobine.fit"><b>Official Website</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/en/hardware"><b>Hardware Recommendations</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/en/documentation"><b>Documentation</b></a> &nbsp;·&nbsp;
  <a href="README.fr.md"><b>Français</b></a> &nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.en.md"><b>Technical Architecture</b></a><br>
  <a href="https://github.com/FantasmaGlad/Bobine/releases/latest"><b>Latest Release (v5.0.0)</b></a> &nbsp;·&nbsp;
  <a href="https://github.com/FantasmaGlad/Bobine/releases/tag/beta"><b>Beta Release</b></a> &nbsp;·&nbsp;
  <a href="https://github.com/FantasmaGlad/Bobine/releases/tag/canary"><b>Canary Release</b></a>
</p>

<p align="center">
  <a href="https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml"><img src="https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://github.com/FantasmaGlad/Bobine/releases/latest"><img src="https://img.shields.io/badge/Release-v5.0.0-brightgreen" alt="Release: v5.0.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue.svg" alt="License: AGPL-3.0"></a>
  <img src="https://img.shields.io/badge/Architecture-Local--first%20%7C%20100%25%20Offline-success" alt="Architecture">
  <img src="https://img.shields.io/badge/Privacy-Zero%20Telemetry-purple" alt="Privacy">
  <img src="https://img.shields.io/badge/Video-4K%2060fps%20Native-orange" alt="Video">
  <img src="https://img.shields.io/badge/Hardware%20Accel-VA--API%20%7C%20VideoToolbox%20%7C%20MediaCodec%20%7C%20QSV-red" alt="Hardware Accel">
  <img src="https://img.shields.io/badge/Browsers-Firefox%20%7C%20Chrome%20%7C%20Edge%20%7C%20Safari-FF7139?logo=firefoxbrowser&logoColor=white" alt="Browsers">
  <a href="https://apt.bobine.fit"><img src="https://img.shields.io/badge/APT%20Repo-apt.bobine.fit-A81D33?logo=debian&logoColor=white" alt="APT Repo"></a>
  <a href="https://github.com/FantasmaGlad/Bobine/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

---

## Quick Download & Native Applications

Install Bobine as a native application on your tablet, workstation, or studio PC in seconds:

| Platform | Format | Architecture | Direct Download / Command | Target Profile & Key Features |
| :--- | :---: | :---: | :---: | :--- |
| ![](https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white) | <sub>`.apk`<br>*(Native Package)*</sub> | <sub>ARM64<br>*(arm64-v8a)*</sub> | <sub>[**Download Bobine-5.0.0.apk**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.apk)</sub> | **Android Tablets & Google Books (Aluminium OS)**<br><sub>Touch coach desk (`/grid`) + HDMI TV cinema (`/cinema`), soon on Google Play Store</sub> |
| ![](https://img.shields.io/badge/Android_TV-009688?style=flat-square&logo=android&logoColor=white) | <sub>`.apk`<br>*(Dedicated TV Package)*</sub> | <sub>ARM 32 & 64-bit<br>*(armeabi-v7a, arm64-v8a)*</sub> | <sub>[**Download Bobine-TV-5.0.0.apk**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-TV-5.0.0.apk)</sub> | **Android TV & Google TV**<br><sub>Leanback TV launcher, D-Pad remote navigation, offline kiosk</sub> |
| ![](https://img.shields.io/badge/Windows_11-0078D4?style=flat-square&logo=windows11&logoColor=white) | <sub>`.exe`<br>*(Installer)*</sub> | <sub>x86-64 & ARM64<br>*(Snapdragon)*</sub> | <sub>[**Bobine-Setup-5.0.0.exe (x86-64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-Setup-5.0.0.exe)<br>[**Bobine-Setup-5.0.0-arm64.exe (ARM64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-Setup-5.0.0-arm64.exe)</sub> | **Windows 11/10 PCs & Qualcomm Snapdragon ARM Laptops**<br><sub>Native x86-64 and ARM64 installer (Snapdragon X Elite / X Plus), tray icon, clamshell mode</sub> |
| ![](https://img.shields.io/badge/Debian-A81D33?style=flat-square&logo=debian&logoColor=white) ![](https://img.shields.io/badge/Ubuntu-E95420?style=flat-square&logo=ubuntu&logoColor=white) | <sub>`.deb`<br>*(Package & Repo)*</sub> | <sub>x86-64 *(amd64)*<br>& ARM64 *(arm64)*</sub> | <sub>[**APT Repo apt.bobine.fit**](https://apt.bobine.fit)<br>[**bobine_5.0.0_amd64.deb**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine_5.0.0_amd64.deb)<br>[**bobine_5.0.0_arm64.deb**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine_5.0.0_arm64.deb)</sub> | **Linux Desktops, ARM64 Workstations & NVIDIA DGX Spark**<br><sub>Official `.deb` packages (`amd64` & `arm64`) and `apt.bobine.fit` repository updates</sub> |
| ![](https://img.shields.io/badge/macOS-000000?style=flat-square&logo=apple&logoColor=white) | <sub>`.dmg`<br>*(Disk Image)*</sub> | <sub>Apple Silicon<br>*(arm64)*</sub> | <sub>[**Download Bobine-5.0.0.dmg**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.dmg)</sub> | **MacBook, Mac mini & iMac**<br><sub>Drag-and-drop `.dmg`, Apple Silicon & Intel, menu bar companion</sub> |
| ![](https://img.shields.io/badge/iOS%20%2F%20iPadOS-000000?style=flat-square&logo=apple&logoColor=white) | <sub>iPadOS App<br>*(Explored Track)*</sub> | <sub>ARM64 (Apple Silicon)</sub> | <sub>*Explored track...*</sub> | **iPads & Apple Tablets (Explored Track)**<br><sub>Touch coach desk prototype with USB-C / Thunderbolt video output</sub> |
| ![](https://img.shields.io/badge/Bobine_Assistant-FFC131?style=flat-square&logo=tauri&logoColor=black) | <sub>Native Binary<br>*(Tauri 2)*</sub> | <sub>x86-64 & ARM64<br>*(Linux)*</sub> | <sub>[**bobine-assistant (x86-64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine-assistant)<br>[**bobine-assistant-arm64 (ARM64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine-assistant-arm64)</sub> | **Management Assistant (GUI)**<br><sub>Network auto-discovery, SSH remote deploy & update tool</sub> |
| ![](https://img.shields.io/badge/Bash_CLI-4EAA25?style=flat-square&logo=gnubash&logoColor=white) | <sub>Shell Script<br>*(Automated)*</sub> | <sub>x86-64 & ARM64</sub> | <sub>`curl -sSL https://bobine.fit/install.sh \| bash`</sub> | **Headless Dedicated Appliance (x86-64 & ARM64)**<br><sub>Automated 18-step install for bare-metal mini PCs and ARM64 stations (Debian 13)</sub> |
| [![](https://img.shields.io/badge/Tor_Browser-7D4698?style=flat-square&logo=torbrowser&logoColor=white)](http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/) | <sub>APT Repo & Mirror<br>*(Tor Network)*</sub> | <sub>x86-64 & ARM64<br>*(amd64 / arm64)*</sub> | <sub>`curl -fsSL https://bobine.fit/install-tor.sh \| bash`<br>[**Tor Mirror (.onion)**](http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/)<br>[**APT Repo (.onion)**](http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/)</sub> | **Tor Network (.onion)**<br><sub>Anonymous APT repo and website mirror without IP exposure</sub> |
| [![](https://img.shields.io/badge/bobine.fit-4285F4?style=flat-square&logo=data%3Aimage/svg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0OCA0OCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4Ij48cGF0aCBmaWxsPSIjNENBRjUwIiBkPSJNNDQgMjRjMCAxMS4wNDUtOC45NTUgMjAtMjAgMjAtNC41MiAwLTguNjgtMS41MDMtMTIuMDMtNC4wNDNsOS40NjctMTYuMzk0QTggOCAwIDAgMCAyNCAzMmM0LjQxOCAwIDgtMy41ODIgOC04eiIvPjxwYXRoIGZpbGw9IiNGQkMwMkQiIGQ9Ik00NCAyNEgyNGE4IDggMCAwIDAtNi45MjggNGwtOS40NjcgMTYuMzk0QTE5LjkyIDE5LjkyIDAgMCAxIDQgMjRDNCAxMy45ODcgMTEuMzg1IDUuNzA0IDIxLjAzNiA0LjIyTDMwLjUwMyAyMC42MUE3Ljk3IDcuOTcgMCAwIDAgMzIgMjR6Ii8%2BPHBhdGggZmlsbD0iI0U1MzkzNSIgZD0iTTI0IDRjNy40MDYgMCAxMy44NiA0LjAyNCAxNy4zIDEwLjAyN0wzMC41MDMgMjAuNjFBOCA4IDAgMCAwIDI0IDE2Yy0zLjE1NSAwLTUuOTE0IDEuODI2LTcuMjUgNC40OUw3LjI4NCA0LjA5NUMxMS44OTIgNC4wMzIgMTcuNjUgNCAyNCA0eiIvPjxjaXJjbGUgY3g9IjI0IiBjeT0iMjQiIHI9IjgiIGZpbGw9IiNGRkYiLz48Y2lyY2xlIGN4PSIyNCIgY3k9IjI0IiByPSI2IiBmaWxsPSIjMTk3NkQyIi8%2BPC9zdmc%2B)](https://bobine.fit) | <sub>Web Portal</sub> | <sub>Universal</sub> | <sub>[**Visit bobine.fit**](https://bobine.fit)</sub> | **Official Website**<br><sub>Getting started guides, hardware recommendations & docs</sub> |
| ![](https://img.shields.io/badge/GitHub-Releases-181717?style=flat-square&logo=github&logoColor=white) | <sub>Source & Binaries</sub> | <sub>Multi-OS</sub> | <sub>[**Browse GitHub Releases**](https://github.com/FantasmaGlad/Bobine/releases/latest)</sub> | **Releases & Source Code**<br><sub>Certified SHA-256 checksums, tarballs & full changelog</sub> |

### Beta & Canary Programs — Early Access

<p align="center">
  <img alt="Stable channel" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/Versions/Stable-cropped-1024.png" width="100"> &nbsp;&nbsp;
  <img alt="Beta channel" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/Versions/Beta-cropped-1024.png" width="100"> &nbsp;&nbsp;
  <img alt="Canary channel" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/Versions/Canary-cropped-1024.png" width="100">
  <br>
  <sub>Stable · Beta · Canary</sub>
</p>

Want to try upcoming features before they reach the stable release? Bobine ships two pre-release channels, in addition to Stable: **Beta**, a batch of features/fixes I curate and publish manually when ready, and **Canary**, a single always-current build rebuilt automatically from the very latest commit on `main` — no curation at all. Neither requires tracking version numbers; an equal or newer stable release always supersedes either one automatically, and you can switch back to Stable at any time with no data loss.

| Channel | Update cadence | Curation | Who it's for | Tag |
| :--- | :--- | :--- | :--- | :---: |
| **Stable** | One release per version, tagged | Fully tested | Production gym playout — the recommended default | `Vx.y.z` |
| **Beta** | Batches, published manually when ready | I curate it myself | Early adopters who want upcoming features without the daily churn | `beta` |
| **Canary** | Every single commit to `main` | None — raw and immediate | Developers and power users who want the absolute latest, accept rough edges | `canary` |

[**Browse the Beta release**](https://github.com/FantasmaGlad/Bobine/releases/tag/beta) · [**Browse the Canary release**](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) — same platforms as above (`.exe`, `.deb`, `.dmg`, `bobine-assistant`, `install.sh`), file names suffixed `-beta`/`-canary` instead of a version number.

How to opt in permanently, so future updates keep offering Beta or Canary builds:
- **Already installed** → Settings → Software Updates → "Update channel", switch to Beta or Canary.
- **Headless appliance installer** → `sudo ./install.sh --channel=beta` or `--channel=canary`
- **Bobine Assistant (remote install wizard)** → pick the channel in the Options step.

Full details on how these channels work (update detection, downgrade behavior, release process): [Technical Architecture § Update Channel](docs/ARCHITECTURE.en.md#7-install-script--systemd-services).

Dedicated pages: [Bobine Stable](https://bobine.fit/en/channels/stable) · [Bobine Beta](https://bobine.fit/en/channels/beta) · [Bobine Canary](https://bobine.fit/en/channels/canary) · [all update channels](https://bobine.fit/en/channels) · [what's new](https://bobine.fit/en/whats-new). Machine-readable current versions: [`latest.json`](https://bobine.fit/latest.json) and the [Atom feed](https://bobine.fit/feed.xml).

---

**The open-source, self-hosted alternative to Les Mills Cinema, Wexer, and Screenly Anthias — professional offline-first video playout, digital signage, and scheduled group-fitness cinema for fitness clubs, gyms, and sports studios.**

Bobine turns any tablet, desktop PC, Mac, or low-cost dedicated mini PC into a complete autonomous broadcast studio:
- **Cinematic 4K 60fps Playout & Gapless A/B Deck Engine**: Schedules and plays group-fitness classes on big screens with a streaming-style catalog, modern Netflix-style home and pause overlay, dual continuous video decoders eliminating all black screens between classes, and multi-OS hardware acceleration (VA-API, VideoToolbox, MediaCodec, QuickSync).
- **Independent Dual Channel & Studio Coach Desk**: Drives a wired display (HDMI TV / projector) and a networked display (Wi-Fi / LAN) simultaneously with separate playout pipelines, or pairs a mobile touch coach desk (`/grid`) with big-screen cinema (`/cinema`).
- **On-Demand Member Kiosk & 5-Star Rating System**: Lets members browse and start workouts on demand from a locked interactive kiosk, submit 5-star ratings on touch screens or on big screens via remote/gamepad, or control music and volume via QR code smartphone remotes.
- **Metrics Dashboard & Live Hardware Telemetry**: Comprehensive attendance and workout analytics (`/metrics`) with completion rates, 24-hour attendance bar charts, and real-time host telemetry (power draw in Watts, temperatures, CPU/GPU and RAM loads with manufacturer, DDR technology and max frequency, and component commercial models).
- **Audio Coach Mode & 24/7 Studio Radio**: Runs audio workouts over dynamic animated motion backgrounds and streams continuous club background music.
- **100% Local-First & Sovereign**: Everything runs directly on your own hardware. Zero cloud dependencies, zero monthly subscriptions, zero telemetry, zero vendor lock-in — engineered for rock-solid 24/7 unattended playback even without internet.

---

## Why Bobine

Group-fitness rooms increasingly run pre-recorded, instructor-led video classes ("virtual classes") on a big screen. Proprietary solutions like Les Mills Cinema or cloud SaaS platforms like Wexer lock operators into closed platforms, recurring per-screen subscriptions, and external dependencies that stop working when the internet drops. Bobine delivers the same in-club experience — scheduled classes, an on-demand kiosk, a polished member experience — while keeping you in full control:

- **You own it.** Your videos, your hardware, your schedule. No monthly fee, no vendor lock-in, no account.
- **It works offline.** Once installed, the club needs no internet connection to run classes.
- **The source is open.** AGPL-3.0-licensed and auditable — the system's future doesn't depend on a vendor's business decisions.
- **It runs on cheap hardware.** A second-hand thin client or mini PC (Dell Wyse 5070 class) is enough — no recurring licence fee per screen.
- **It is unattended.** Auto-starts on power-up, recovers from power loss, and restarts a failed component on its own.
- **Tor Network (.onion) Distribution & Privacy.** Both the website mirror and the APT package repository are published as onion services for gyms desiring zero IP disclosure or operating behind restrictive firewalls.

### Positioning & Alternatives
- **Alternative to proprietary fitness subscriptions (Les Mills Cinema, Wexer Virtual, Fitness On Demand, Radical Fitness / franchise video packages like Yako)**: Bobine removes recurring monthly license fees and catalog constraints. Operators have full freedom over their video content (custom coach recordings or independent libraries), timetables, and studio branding, with 100% offline local SSD reliability.
- **Alternative to generic digital signage (Screenly Anthias, Yodeck, Xibo, TouchPlayer, Waves System)**: Unlike passive billboard or menu loopers, Bobine is purpose-built for fitness operations: power-loss recovery & anti-screensaver, interactive member on-demand touch kiosk, smartphone coach remote control via local QR code, and 24/7 background audio with crossfade and automated voice announcements, running smoothly on cost-effective x86-64 mini PCs with VA-API hardware decoding.
- **Community & Directory**: Also listed on [AlternativeTo](https://alternativeto.net/software/fantasmaglad-bobine/about/) for open-source recommendations and reviews.

Typical users: boutique studios, gyms, hotel and corporate fitness rooms, physiotherapy and rehab spaces, dance and cycling studios — anyone who plays scheduled or on-demand fitness videos on a screen, and anyone looking for a sovereign, self-hosted alternative without the subscription.

Bobine is program-agnostic: class categories are free-form, so it fits any catalogue of group-fitness, cycling, strength, mobility or wellbeing classes.


---

## Features

- **Video scheduling** — build a weekly timetable; classes start automatically at the right time on the right screen.
- **On-demand cinema kiosk** — a member-facing full-screen browser to pick and start a class themselves with instant playback and power outage recovery.
- **Two independent display outputs** — drive a wired screen (HDMI) and a networked screen separately, each with its own content.
- **Mobile remote** — control playback (play, pause, seek, next) from any phone on the local network: "Now playing" widget, launching a class with a preview (thumbnail, duration), subtitle choice and chapter jumps.
- **Subtitles & chapters** — `.srt`/`.vtt` tracks in several languages per class, chapters imported (JSON, WebVTT or "05:00 Title" text) or extracted from the video file, progress marks and an on-screen banner.
- **Universal input support (Gamepads, Remotes, Mouse, Touch)** — the member cinema (`/cinema`), coach grid (`/grid`), interactive kiosk (`/kiosk`), and radio screen (`/radio`) respond instantly to all devices: game controllers (Xbox, PlayStation, 8BitDo, Switch Pro via HTML5 Gamepad API), physical USB/Bluetooth media remotes (arrows, OK, back, play/pause, seek, volume), mouse, and touchscreens.
- **Coach audio mode** — play audio-only classes over the room speakers with an animated or still visual background on screen.
- **Built-in radio** — a Spotify-style 24/7 background-music player with crossfade, shuffle, repeat, and scheduled spoken reminders ("re-rack your weights", etc.).
- **Two independent radio outputs** — the wired radio and the network radio each have their own playlist, volume, reminders and schedule: handy for running several radios in the room. A **Radio** switch on the wired output turns the physical screen into a radio station, on demand.
- **Equalizer and bass** — 5-band equalizer, bass boost, loudness, overload protection and presets (Voice, Bass boost, Cardio / gym…), set per output, with no extra weight: processing is done by the player.
- **Simple library management** — drag-and-drop import, bulk upload, free-form categories, grouped selection, per-file import progress, automatic thumbnails.
- **Local-first and resilient** — automatic recovery after a reboot or power cut, and a health watchdog that restarts a dead component.
- **Web admin + zero client install** — administer everything from a browser; member screens and remotes are just web pages.
- **Screen Wake Lock API** — prevents screen sleep automatically during workouts and radio playback across all modern browsers.
- **Hardware-accelerated transcoding** — native MediaCodec (Android), VideoToolbox (Apple Silicon M1-M4), VA-API (Linux), and QuickSync (Windows), with ultrafast CPU fallback.
- **Full native quality (2K & 4K)** — strict preservation of ultra-high definition resolutions without downscaling, standardized into fast-start MP4.
- **Reactive import cancellation & live ETA** — 1-click cancel (X) with instant FFmpeg SIGTERM/SIGKILL, orphan temp file purge, and real-time remaining duration estimation.
- **Crisp 1080p thumbnails & fast seek** — Full HD previews on 4K displays and closed GOP keyframe intervals for instant playback seeking.

---

## Supported Hardware

Bobine is lightweight, robust, and designed to run smoothly on a wide spectrum of modern, legacy, or refurbished hardware (native **x86-64** and **ARM64** architectures):

- **Laptops (Windows 11/10 x86-64 & ARM64 Snapdragon, macOS, Linux & Google Books)**:
  - **All x86-64 PC Laptops**: HP Pavilion, Acer Aspire, Lenovo IdeaPad/ThinkPad, Dell Inspiron/Latitude, ASUS Vivobook, etc.
  - **Qualcomm Snapdragon ARM Laptops**: devices running **Windows 11 ARM64** (`Bobine-Setup-5.0.0-arm64.exe`) or **Linux ARM64** (`bobine_5.0.0_arm64.deb`) powered by **Qualcomm Snapdragon X Elite / X Plus** processors (Surface Laptop 7, Lenovo Yoga Slim 7x, ThinkPad T14s Gen 6, ASUS Vivobook S 15, Dell XPS 13 / Inspiron ARM, HP OmniBook X...).
  - **Google Books (Google Book laptops / Aluminium OS)**: native support via the Android ARM64 application (`Bobine-5.0.0.apk`, and soon available natively on the Google Play Store) as well as via the built-in Debian Linux ARM64/x86-64 subsystem.
  - **Apple MacBook Range**: MacBook Air & MacBook Pro (Apple Silicon M1, M2, M3, M4, and Intel models).
  - **Two flexible operating modes**:
    - *Studio Console Mode (Dual Display)*: The laptop screen becomes an interactive control console (`/grid` with touch/trackpad/mouse) for selecting and managing classes, while the HDMI output streams clean full-screen video (`/cinema`) to the studio projector or TV with zero windows or cursor clutter.
    - *Headless Clamshell Mode*: The laptop sits closed in a rack or equipment cabinet, streaming uninterrupted full-screen playback to the TV without sleeping, remotely controlled via any smartphone (`/mobile` or `/coach`).
- **Android Tablets & ARM Touch Kiosks (All-in-One Touch Playout)**:
  - **Xiaomi Pad 8** (official reference tablet, validated on testbeds and in real gym conditions), **Xiaomi Pad 6 & 7**, Samsung Galaxy Tab S-series, Lenovo Tab P-series (ARM64 devices featuring USB-C DisplayPort alternate mode to HDMI).
  - *Two modes available*: Interactive touch console (`/grid` on tablet + clean `/cinema` on TV/projector), or Headless mode featuring a clean standby screen with an instant toggle switch.
- **Android TV, Google TV & Media Streaming Boxes (Direct-to-TV Playout)**:
  - **Chromecast with Google TV** (HD / 4K), **Nvidia Shield TV / Pro**, **Xiaomi TV Box S (2nd Gen)**, **Nokia Streaming Box 8000/8010**, **Strong Leap-S3**, smart TVs running Android TV & Google TV (Sony, Philips, TCL, Hisense...).
  - *Two flexible operating modes*:
    - *Network Kiosk Client (Recommended & zero-config)*: Connects to your studio's primary Bobine server (PC, Mac, Mini PC, or Tablet on the same Wi-Fi/LAN) to deliver the interactive `/kiosk` UI, fully navigable with the original TV remote.
    - *Standalone Dedicated Server*: Runs the full Bobine backend engine locally (FastAPI + SQLite). **External storage requirement**: Due to limited onboard flash storage (4–8 GB eMMC), plug in a **USB 3.0 flash drive or external SSD** (FAT32/exFAT) via USB-OTG to store class media without filling up internal storage.
- **Desktop PCs, ARM64 Workstations & Studio Computers**:
  - Any standard Windows or Linux x86-64 or ARM64 tower / desktop PC (4 GB+ RAM).
  - **Linux ARM64 Workstations & Mini PCs**: **NVIDIA DGX Spark (Grace Blackwell GB10)**, NVIDIA Jetson Orin, Raspberry Pi 5 (8 GB / 16 GB), Orange Pi 5 Max, Radxa Rock 5B, etc. (via the `arm64` `.deb` package, `apt.bobine.fit` repo, `install.sh`, or `bobine-assistant-arm64`).
  - Apple **Mac Mini** & **iMac** (exceptionally quiet, compact playout machines for fitness studios).
- **Dedicated Mini PCs & Thin Clients (Ideal for 24/7 autonomous gym setups)**:
  - Affordable refurbished x86-64 appliances: **Dell Wyse 5070**, **HP ProDesk 400/600 DM**, **Lenovo ThinkCentre Tiny**, **Beelink Mini S12/EQ12**, Intel NUC.
  - ARM64 Mini PCs & SBCs: **NVIDIA DGX Spark**, **Raspberry Pi 5**, **Orange Pi 5 Max**, **Radxa Rock 5B**.
  - 100% autonomous unattended Linux appliance (Debian 13 x86-64 & ARM64) with auto-start, power-loss recovery and continuous playback without sleep.
- **Screens, Projectors & Digital Displays**:
  - Any gym TV, large-format display, studio monitor, or projector connected via **HDMI**, **DisplayPort**, or **USB-C DisplayPort**.
  - Interactive touch screens via USB/HDMI for member self-service.
  - Ancillary screens: any local smart TV, tablet, or laptop browsing over Wi-Fi.
- **Audio Playout & Sound Systems**:
  - Standard 3.5mm analog jack, HDMI audio, external USB sound card, Bluetooth speaker, or direct line-in connection to studio amplifier / mixer.
- **Remote Controls & Handheld Operation**:
  - **Universal mobile web remote**: instant QR-code access from any iOS or Android smartphone with zero app installation.
  - **Physical USB remotes**: out-of-the-box support for wireless presentation remotes and media Air Mice (2.4 GHz USB dongle recognized as a native keyboard without drivers).

> For advanced technical benchmarks, multi-OS hardware acceleration pipelines, and appliance systemd architecture, see the dedicated [**Technical Architecture Documentation (docs/ARCHITECTURE.en.md)**](docs/ARCHITECTURE.en.md).

### Supported Browsers

<p align="left">
  <a href="https://www.mozilla.org/firefox/"><img src="Assets/Images/firefox.svg" alt="Firefox" width="56" align="left" hspace="12" /></a>
  <b>Bobine proudly supports Firefox.</b> The admin interface and every player opened from another device (<code>/radio</code>, <code>/kiosk</code>, <code>/cinema</code>, <code>/coach</code>, <code>/mobile</code>) target Firefox (current release and ESR, desktop and Android) alongside Chrome, Edge and Safari — one codebase, feature detection only, no browser sniffing.
</p>

| Browser | Status |
|---|---|
| **Firefox** (Windows, macOS, Linux, Android — release, previous release & ESR) | **Supported** — verified end to end on Firefox 157 / Linux (17 automated checks in CI, including resuming an upload after a network cut). Windows, macOS, Android and ESR are not yet measured (the import slowdown once reported was traced to another program's memory leak on that PC, not to Bobine) |
| Chrome / Chromium / Edge | Supported (reference kiosk engine on the headless appliance) |
| Safari / iOS browsers (WebKit) | Supported on a best-effort basis |
| Firefox derivatives (LibreWolf, Waterfox, Floorp, Zen) | Best effort (same Gecko engine) |

Hardware video decoding is browser- and OS-dependent (HEVC/AV1 in particular): when a browser cannot decode a video, Bobine serves a compatible H.264 version (produced on demand, original untouched) — see *Settings → Browser compatibility* for a local diagnostic. See [`scripts/browser-bench/`](scripts/browser-bench/README.md) to reproduce the Firefox measurements. *Firefox is a trademark of the Mozilla Foundation; its logo is used here only to state compatibility, with no affiliation or endorsement.*

---

## Installation & Deployment Options

Bobine offers distinct deployment paths to match your exact setup:

1. **Option 1: Native Applications (Simplest for tablets, PCs & laptops)**: Android & Google Books (`.apk`), Windows 11/10 x86-64 & ARM64 Snapdragon (`.exe`), Linux Desktop x86-64 & ARM64 (`.deb` & APT repo), and macOS (`.dmg`). Installs with 1 click, runs completely offline, and integrates seamlessly with your operating system.
2. **Option 2: Dedicated Headless Linux Appliance (Best for autonomous clubs & fine control)**: Turns a bare-metal mini PC x86-64 (such as a Dell Wyse 5070) or ARM64 station (NVIDIA DGX Spark, Raspberry Pi 5, Orange Pi 5 Max) into a dedicated, unattended appliance booting directly into a locked full-screen X11 kiosk with automated power-loss recovery and anti-screensaver. Fast 1-line CLI install.
3. **Option 3: Bobine Assistant, Graphical Installer (`assistant/`)**: A cross-platform graphical tool (x86-64 & ARM64) to discover, inspect, and deploy appliances over the local network via SSH.

---

### Option 1 — Native Applications (Android, Google Books, Windows, Linux & macOS)

#### On Android (Tablets & Touch Kiosks) and Google Books (Aluminium OS)

See also [Bobine on Google Book](https://bobine.fit/en/google-book).

1. **Download** [**`Bobine-5.0.0.apk`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.apk) directly on your Android tablet or **Google Book (Aluminium OS)** laptop (soon available natively on the Google Play Store; on Google Books, you can also install the `.deb` package via the built-in Debian Linux ARM64/x86-64 subsystem).
2. **Install the APK** (enable installation from unknown sources if prompted).
3. **Launch Bobine**:
   - The persistent `ForegroundService` starts the embedded FastAPI backend (CPython 3.13 via Chaquopy) and automatically acquires an mDNS multicast lock.
   - The tablet screen displays the touch-optimized `/grid` interface for selecting, queuing, and controlling workouts.
   - Plug a USB-C to HDMI adapter or dock into your TV / projector: Bobine automatically routes the dedicated, clean full-screen `/cinema` feed to the external display.
   - Other devices on the same Wi-Fi can access the studio remote or admin panel at `http://bobine.local:8000`.

#### On Android TV & Google TV (Streaming Boxes, Sticks & Smart TVs)

See also the web page [Bobine on Android TV & Google TV](https://bobine.fit/en/android-tv) (download table and FAQ).

1. **Download** [**`Bobine-TV-5.0.0.apk`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-TV-5.0.0.apk) (or from the [latest GitHub release](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Install the APK on your TV or Streaming Box**:
   - Transfer the file via a USB flash drive (using a file manager like *AnExplorer* or *File Commander*), or wirelessly via tools such as *Send Files to TV* or *Downloader*.
   - Enable installation from unknown sources under *Settings → Security & Restrictions* on your TV.
3. **Launch Bobine from the TV Home Screen**:
   - The app appears directly in your Android TV / Google TV apps row thanks to native Leanback launcher support and official 16:9 banner.
   - **Automatic Fullscreen TV UI**: Bobine automatically loads the TV-optimized kiosk UI (`/kiosk`), fully controllable with the standard D-Pad remote (arrow keys, center OK, Back key to return to previous views).
   - **Removable External Storage (Standalone Server Mode)**: When using the TV box as an autonomous, self-hosted server, plug in a USB 3.0 flash drive or external SSD formatted in FAT32 or exFAT. Bobine automatically detects and selects the external drive for media storage without filling up internal eMMC flash memory.

#### On Windows (11, 10, Windows IoT & Qualcomm Snapdragon ARM PCs)

1. **Download** the installer matching your processor architecture:
   - **x86-64 PC (Intel / AMD)**: [**`Bobine-Setup-5.0.0.exe`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-Setup-5.0.0.exe)
   - **ARM64 PC (Qualcomm Snapdragon X Elite / X Plus)**: [**`Bobine-Setup-5.0.0-arm64.exe`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-Setup-5.0.0-arm64.exe)
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

#### On Linux Desktop (Debian, Ubuntu, Linux Mint & derivatives — x86-64 & ARM64)

**Recommended Method — Official APT Repository ([apt.bobine.fit](https://apt.bobine.fit), `amd64` & `arm64` architectures):**
Configure the official GPG-signed APT repository to install Bobine (on x86-64 PCs, Linux ARM Snapdragon laptops, **NVIDIA DGX Spark** workstations, Raspberry Pi 5, etc.) and automatically receive software updates via regular `sudo apt upgrade`:
```bash
# 1. Official GPG keyring
curl -fsSL https://apt.bobine.fit/bobine.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/bobine.gpg

# 2. Add official APT repository (Stable channel; replace 'stable' with 'beta' or 'canary' for pre-releases)
echo "deb [signed-by=/etc/apt/keyrings/bobine.gpg] https://apt.bobine.fit/ stable main" | sudo tee /etc/apt/sources.list.d/bobine.list

# 3. Update & Install
sudo apt update && sudo apt install bobine
```

**Secure Option — APT Repository over Tor (.onion):**

Details and checks: [Bobine on Tor](https://bobine.fit/en/tor).
To install and update Bobine with end-to-end privacy without revealing your facility's IP address:
```bash
sudo apt install apt-transport-tor
curl -fsS --socks5-hostname 127.0.0.1:9050 http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/bobine.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/bobine.gpg
echo "deb [signed-by=/etc/apt/keyrings/bobine.gpg] tor+http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/ stable main" | sudo tee /etc/apt/sources.list.d/bobine-onion.list
sudo apt update && sudo apt install bobine
```
Or via the automated script (Tor-routed GPG fingerprint validation):
```bash
curl -fsSL https://bobine.fit/install-tor.sh | bash
```

**Alternative Method — Standalone `.deb` Package (Offline or 1-click install):**
1. **Download** [**`bobine_5.0.0_amd64.deb`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine_5.0.0_amd64.deb) (x86-64 PC) or [**`bobine_5.0.0_arm64.deb`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine_5.0.0_arm64.deb) (ARM64: NVIDIA DGX Spark, Snapdragon, Raspberry Pi 5, etc.).
2. **Install the package** via the Ubuntu App Center / GNOME Software by double-clicking the file, or via the terminal:
   ```bash
   sudo apt install ./bobine_*.deb
   ```
   *(All runtime dependencies including `ffmpeg` are resolved automatically, and multi-resolution icons are integrated into the system theme).*

**Launch & Desktop Integration:**
- Launch Bobine from your **Desktop** shortcut, the Applications menu, or by typing `bobine` in a terminal.
- The Bobine tray icon appears in your status bar / system tray.
- XDG autostart is automatically configured at desktop login.
- Your media files, database, and settings live cleanly in your user directory following the XDG specification: `~/.local/share/bobine/`.

#### On macOS (Apple Silicon - M1/M2/M3/M4)

1. **Download** [**`Bobine-5.0.0.dmg`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.dmg) (or from the [latest GitHub release](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Open the .dmg** and drag `Bobine.app` into your **Applications** folder.
3. **Launch Bobine** from Applications, your **Desktop** (shortcut created automatically), or Spotlight.
   - *First launch*: Since Bobine is free open-source software without a paid Apple Developer certificate (not notarized), Gatekeeper will block the first launch. Depending on your macOS version you'll see one of two messages:
     - **"Bobine was blocked" / "from an unidentified developer"** → Open **System Settings → Privacy & Security**, scroll down, click **Open Anyway**, confirm.
     - **"Bobine.app" is damaged and can't be opened. You should move it to the Trash"** → this is **not** a corrupted download — it's Gatekeeper's (misleading) wording for the same unsigned-app situation, and it offers no "Open Anyway" button. Fix it from Terminal: `xattr -cr /Applications/Bobine.app`, then launch it again.
   - Bobine configures a LaunchAgent so it starts automatically at login. A menu bar icon lets you open the admin dashboard, start the full-screen kiosk, restart the engine, or quit.
4. **Open the interface**: `http://bobine.local` from any device on your local network (or `http://127.0.0.1:8000` locally). Data is stored in `~/Library/Application Support/Bobine`.

---

### Dedicated Servers & Headless Appliances — Advanced Installation Methods

For studios, fitness clubs, and integrators deploying autonomous 24/7 kiosks on dedicated low-cost x86-64 mini PCs (Dell Wyse 5070, HP ProDesk DM...) or Linux ARM64 workstations (**NVIDIA DGX Spark**, NVIDIA Jetson Orin, Raspberry Pi 5, Orange Pi 5 Max, Radxa Rock 5B) without desktop overhead:

| Method | Type | Target Hardware | Deployment Process | Key Features |
| :--- | :---: | :---: | :--- | :--- |
| <img src="Assets/Images/bash.svg" width="20" height="20" valign="middle" alt="Bash"> **Bash Installer (CLI)** | <sub>Shell Script</sub> | <sub>Debian 13 (x86-64 & ARM64)</sub> | <sub>`curl -sSL https://bobine.fit/install.sh \| bash`</sub> | <sub>• Full 18-step automated sequence</sub><br><sub>• Hardware 4K decoding (&lt; 8% CPU)</sub><br><sub>• Power-loss recovery & anti-screensaver</sub><br><sub>• Locked X11 fullscreen kiosk without screensaver</sub><br><sub>• Auto-healing systemd services</sub> |
| <img src="Assets/Images/network.svg" width="20" height="20" valign="middle" alt="Network"> **Bobine Assistant (Tauri)** | <sub>Desktop App<br>*(Tauri 2)*</sub> | <sub>Windows, macOS & Linux<br>*(x86-64 & ARM64)*</sub> | <sub>GUI wizard via SSH remote deployment</sub> | <sub>• Full network scan — every device (hostname, IP, OS, open ports)</sub><br><sub>• SSH via password, imported key file, or auto-detected local keys</sub><br><sub>• Live hardware audit (CPU, GPU, RAM, storage)</sub><br><sub>• 5-step guided visual orchestrator</sub> |

#### Option 2 — Dedicated Headless Linux Appliance (Mini PC x86-64 & ARM64 / Debian 13)

> **For studio operators seeking 100% independence, zero manual intervention, and fine hardware management.**  
> This mode turns a low-cost refurbished x86-64 mini PC (such as a Dell Wyse 5070, HP ProDesk DM, or Lenovo Tiny) or an ARM64 workstation/SBC (**NVIDIA DGX Spark**, Raspberry Pi 5, Orange Pi 5 Max, Radxa Rock 5B) into a dedicated 24/7 video appliance that boots straight into a full-screen hardware-accelerated kiosk without any desktop overhead.

##### 1. Minimal Debian 13 Setup
1. **Download** the Debian 13 "Trixie" *netinst* ISO (`amd64` or `arm64`, ~700 MB) from <https://www.debian.org/download>.
2. **Flash it to a USB stick** (8 GB+) using [balenaEtcher](https://etcher.balena.io/) or `dd`.
3. **Install on the mini PC**: In the software selection step, uncheck all desktop environments and keep only **SSH server** and **standard system utilities**.

##### 2. Fast 1-Line CLI Installation
Connect to the mini PC directly or via SSH as your standard non-root user and run:

```bash
# Automated 1-line installation (stable channel):
curl -fsSL https://bobine.fit/install.sh | bash

# Same, but on the Beta channel (curated early access):
curl -fsSL https://bobine.fit/install.sh | bash -s -- --channel=beta

# Or the Canary channel (every commit on main, untested):
curl -fsSL https://bobine.fit/install.sh | bash -s -- --channel=canary
```

The script fetches the code into `~/Bobine` (installing `git`/`curl` first if the system is minimal), asks for `sudo` by itself, shows live progress with a spinner and per-step timings, waits for any running `unattended-upgrades`, fixes a drifted system clock, and finishes with the admin URL **and a QR code** to open it from a phone. Re-running it is safe: it updates an existing installation in place. Add `--dry-run` to preview every action.

*(Alternatively, for full source control and custom flags: `git clone https://github.com/FantasmaGlad/Bobine.git && cd Bobine && sudo ./install.sh`).*

**What `install.sh` configures automatically:**
- System packages: Python virtualenv, Uvicorn, SQLite, Chromium, FFmpeg with VA-API hardware decoding.
- Full-screen X11 kiosk auto-login with screen saver suppression.
- Automated playback: auto-start on boot, power-loss recovery, and screen-saver suppression.
- Systemd services (`bobine-backend.service`, `bobine-kiosk.service`, `bobine-audio-guard.service`).
- System health watchdog: automatic restart upon unexpected failures and full power-loss recovery.

---

#### Option 3 — Bobine Assistant, Graphical Installer (`assistant/`)

> **Deploy your club appliances remotely from your own computer, without touching a terminal.**

Located in [`assistant/`](assistant/) (available natively for **Windows**, **Linux x86-64** (`bobine-assistant`), **Linux ARM64** (`bobine-assistant-arm64`), and **macOS**), the **Bobine Assistant** desktop application guides the appliance deployment end to end:

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
- **Radio** — open `/radio?channel=network` on a dedicated device to play background music continuously (`/radio` remains an alias); `/radio?channel=cable` is the radio of the wired output, enabled by the *Radio* button of *Wired Output*. Control and sound settings from the admin *Radio* tab.
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

## How it works

Bobine is a single host machine on your local network running:

- a **FastAPI** backend with **SQLite** for storage;
- a **Chromium** kiosk in full screen (X11) for the wired screen (on headless appliances);
- a **Next.js** admin panel, member kiosk, and mobile remote, all served as static pages from the same machine.

Other screens (networked display, member remotes, the admin PC) are ordinary web browsers pointing at the Bobine host. Media never leaves your network.

For the full architecture, data model, network contract and API reference, see **[docs/ARCHITECTURE.en.md](docs/ARCHITECTURE.en.md)**.

---

## Security

Report vulnerabilities privately, never in a public issue: use [GitHub private vulnerability reporting](https://github.com/FantasmaGlad/Bobine/security/advisories/new) or write to [security@bobine.fit](mailto:security@bobine.fit). Reports containing exploitable details must be encrypted with the OpenPGP key `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2` (Ed25519, expires 2028-10-06), published in [`docs/security/`](docs/security/bobine-security-public-key.asc), at <https://bobine.fit/.well-known/security.asc>, at <https://security.bobine.fit>, and through `gpg --locate-keys security@bobine.fit`: check that the fingerprint matches on at least two channels. Create your own key pair and attach your public key so that we can reply encrypted. Full policy, scope and timelines: [SECURITY.md](SECURITY.md).

---

## License

Bobine is free software licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** — see [`LICENSE`](LICENSE). If you run a modified version to provide a network service, you must make your modified source available under the same license.

---

## FAQ

**What is Bobine?** An open-source (AGPL-3.0), self-hosted, offline-first video playout system for gyms and fitness studios: scheduled classes, an on-demand member kiosk, a coach console and 24/7 studio radio. It is a free alternative to Les Mills Cinema, Wexer and Screenly Anthias.

**What is the latest version?** The current Stable, Beta and Canary versions are listed in [`latest.json`](https://bobine.fit/latest.json) and on [bobine.fit/en/whats-new](https://bobine.fit/en/whats-new), read straight from GitHub Releases.

**Does it run on Android TV?** Yes, from Android 14: a dedicated `Bobine-TV` APK installs on Android TV and Google TV boxes and sticks, 32-bit and 64-bit ARM. See [Bobine on Android TV](https://bobine.fit/en/android-tv).

**Does it run on a Google Book?** Yes, through the native Android app. See [Bobine on Google Book](https://bobine.fit/en/google-book).

**What is Bobine Canary?** The rolling update channel, rebuilt on every commit to `main` with no curation. See [Bobine Canary](https://bobine.fit/en/channels/canary).

**Can I install it over Tor?** Yes on Debian, Ubuntu and Mint: the APT repository and the website are also onion services. See [Bobine on Tor](https://bobine.fit/en/tor).

**Does it need internet or an account?** No: after installation it runs fully offline, with no account and no telemetry.

---

## Status and roadmap

Bobine is in active use in production on dedicated hardware and desktop workstations.

To maximize hardware portability and reduce the equipment footprint in fitness studios, the engineering roadmap actively explores porting Bobine to standalone touch tablets capable of wired video playout:
* **Android Tablets with USB-C DisplayPort** (e.g. Xiaomi Pad 6, 7, or 8, Samsung Galaxy Tab S9/S10): Embedding the FastAPI backend locally via Chaquopy and outputting the video feed to the studio display or projector via Android's Presentation API.
* **Apple iPads with Thunderbolt / USB-C Video** (e.g. iPad Pro M1/M2/M4 with Thunderbolt / USB 4, iPad Air M2 with DisplayPort over USB-C): A single cable or powered dock connects the iPad to the projector, dedicating the touch interface to coach controls while driving full video playout to the studio room.

Issues and contributions are welcome on the [GitHub repository](https://github.com/FantasmaGlad/Bobine), under the terms of our [Contributing guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md). You can also discover and review the project on [AlternativeTo](https://alternativeto.net/software/fantasmaglad-bobine/about/).

---

<sub>**Keywords:** open-source Les Mills Cinema alternative, Screenly Anthias alternative for gyms, Wexer Virtual alternative, Fitness On Demand open-source alternative, franchise workout video playout (Radical Fitness, Yako, Les Mills Virtual), self-hosted gym digital signage, group fitness class scheduling software, on-demand gym cinema kiosk, virtual coach player, boutique fitness studio video automation, indoor cycling video playout, power-loss recovery and anti-screensaver, x86-64 thin client, Dell Wyse 5070 video player, offline-first media player, local-first fitness system, background music player for gyms, crossfade gym radio, FastAPI, Next.js, Tauri desktop installer, Windows 11 desktop app, macOS Apple Silicon app, Linux Debian Ubuntu .deb package, cross-platform gym video signage, zero subscription gym software.</sub>
