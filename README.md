# Bobine

<p align="center">
  <img alt="Bobine" src="Assets/Images/LogoBanniere.png" width="100%">
</p>

<p align="center">
  <b>The open-source, self-hosted and 100% offline video playout, member kiosk, coach console, and 24/7 radio system for fitness clubs, gyms, and sports studios.</b>
</p>

<p align="center">
  <a href="https://bobine.fit"><b>Official Website</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/en/download"><b>Downloads</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/en/documentation"><b>User Documentation</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/en/hardware/aliexpress"><b>Recommended Hardware</b></a> &nbsp;·&nbsp;
  <a href="README.fr.md"><b>Français</b></a> &nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.en.md"><b>Technical Architecture</b></a>
</p>

<p align="center">
  <a href="https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml"><img src="https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://github.com/FantasmaGlad/Bobine/releases/latest"><img src="https://img.shields.io/github/v/release/FantasmaGlad/Bobine?label=Stable&color=brightgreen" alt="Latest Stable release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue.svg" alt="License: AGPL-3.0"></a>
  <img src="https://img.shields.io/badge/Architecture-100%25%20Offline-success" alt="100% Offline">
  <img src="https://img.shields.io/badge/Privacy-Zero%20Telemetry-purple" alt="Zero Telemetry">
  <a href="https://packages.bobine.fit"><img src="https://img.shields.io/badge/Linux%20Repos-packages.bobine.fit-A81D33?logo=linux&logoColor=white" alt="Linux Repositories"></a>
</p>

---

## Why Bobine?

Group-fitness rooms and cycling studios run pre-recorded video classes ("virtual classes") on large screens or projectors. Proprietary solutions require monthly subscriptions per screen, closed catalogs, and a permanent internet connection.

**Bobine gives your studio the same cinema-grade experience — free of charge, without any subscription, and under your full control:**

- **You own everything** — your videos, your schedule, your club branding, and your hardware. No account, no license fee, no vendor lock-in.
- **100% Offline** — once installed, your studio needs no internet connection to play scheduled classes, run the member kiosk, or stream background radio.
- **Runs on the hardware you already have** — installs in seconds on Windows, macOS, Linux, Android tablets, Google Books, Android TV boxes, or a refurbished mini PC.
- **Unattended 24/7 reliability** — starts automatically when powered on and resumes playback after a power cut without human intervention.

---

## Download & Install

Native application for computers, tablets, TVs and mini PCs. Stable 5.0.7 below; every channel and file on [**bobine.fit/en/download**](https://bobine.fit/en/download).

| Platform | Download | Requirements |
| :--- | :--- | :--- |
| <img src="Assets/Icons/os/windows.svg" width="20" height="20" valign="middle" alt="Windows"> **Windows** 10 & 11 | [x64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-Setup-5.0.7.exe) · [ARM64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-Setup-5.0.7-arm64.exe) | `.exe` installer, Snapdragon supported |
| <img src="Assets/Icons/os/apple.svg" width="20" height="20" valign="middle" alt="macOS"> **macOS** | [Apple Silicon](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-5.0.7.dmg) | M1 or newer, `.dmg` |
| <img src="Assets/Icons/distros/debian.svg" width="20" height="20" valign="middle" alt="Debian"> **Debian, Ubuntu** | [APT](https://packages.bobine.fit/debian/) · [amd64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine_5.0.7_amd64.deb) · [arm64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine_5.0.7_arm64.deb) | glibc 2.38+ (Debian 13, Ubuntu 24.04) |
| <img src="Assets/Icons/distros/fedora.svg" width="20" height="20" valign="middle" alt="Fedora"> **Fedora, RHEL** | [DNF](https://packages.bobine.fit/fedora/) · [x86_64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-5.0.7-1.x86_64.rpm) · [aarch64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-5.0.7-1.aarch64.rpm) | glibc 2.38+ |
| <img src="Assets/Icons/distros/arch.svg" width="20" height="20" valign="middle" alt="Arch Linux"> **Arch Linux** | [pacman](https://packages.bobine.fit/arch/) · [x86_64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-5.0.7-1-x86_64.pkg.tar.zst) · [aarch64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-5.0.7-1-aarch64.pkg.tar.zst) | glibc 2.38+ |
| <img src="Assets/Icons/os/android.svg" width="20" height="20" valign="middle" alt="Android"> **Android** | [APK](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-5.0.7.apk) | Android 14+, ARM64 |
| <img src="Assets/Icons/os/androidtv.svg" width="20" height="20" valign="middle" alt="Android TV"> **Android TV, Google TV** | [APK TV](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-TV-5.0.7.apk) | ARM 32 and 64-bit |
| <img src="Assets/Images/bash.svg" width="20" height="20" valign="middle" alt="Mini PC"> **Mini PC appliance** | [install.sh](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/install.sh) · [assistant x64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-assistant) · [ARM64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-assistant-arm64) | Debian 13 |
| <img src="Assets/Icons/os/tor.svg" width="20" height="20" valign="middle" alt="Tor"> **Tor (.onion)** | [website](http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/) · [packages](http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/) | Tor Browser or tor |

### One-command install

<img src="Assets/Icons/tools/powershell.svg" width="20" height="20" alt="PowerShell"> Windows (PowerShell): installs Stable after checking its SHA-256 digest.

```powershell
irm https://github.com/FantasmaGlad/Bobine/releases/download/canary/install.ps1 | iex
```

On Windows PowerShell 5.1 with a .NET runtime older than 4.7, run `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12` before `irm`; the script cannot change the TLS version of the request that downloads it.

Another channel (the pipe does not forward parameters):

```powershell
& ([scriptblock]::Create((irm https://github.com/FantasmaGlad/Bobine/releases/download/canary/install.ps1))) -Channel beta
```

Through Tor (PowerShell 7.2+, Tor Browser open; `-TorPort 9050` for the tor service):

```powershell
$script = irm https://github.com/FantasmaGlad/Bobine/releases/download/canary/install.ps1 -Proxy socks5://127.0.0.1:9150
& ([scriptblock]::Create($script)) -Tor
```

<img src="Assets/Icons/tools/homebrew.svg" width="20" height="20" alt="Homebrew"> macOS (Homebrew):

```bash
brew install --cask fantasmaglad/bobine/bobine
```

Through Tor:

```bash
ALL_PROXY=socks5h://127.0.0.1:9050 brew install --cask fantasmaglad/bobine/bobine
```

<img src="Assets/Icons/os/linux.svg" width="20" height="20" alt="Linux"> Linux: signed repositories, instructions on [packages.bobine.fit](https://packages.bobine.fit). Through Tor, repositories and signing key over the onion mirror:

```bash
curl --socks5-hostname 127.0.0.1:9050 -fsSL http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/install-tor.sh | bash
```

<img src="Assets/Images/bash.svg" width="20" height="20" alt="Mini PC"> Mini PC appliance (Debian 13):

```bash
curl -fsSL https://bobine.fit/install.sh | bash
```

Script fetched from the onion mirror (the installation itself then uses the regular network):

```bash
curl --socks5-hostname 127.0.0.1:9050 -fsSL http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/install.sh | bash
```

<img src="Assets/Icons/os/tor.svg" width="20" height="20" alt="Tor"> Through Tor, GitHub and Homebrew see a Tor exit instead of your address.

---

## Key Features

- **Weekly Class Timetable** — Schedule your group classes across the week; workouts start automatically on time on the right screen.
- **Interactive Member Kiosk (`/kiosk` & `/cinema`)** — Let members browse your catalog by category and start a class on demand using a touch screen, TV remote, gamepad, or mouse, with gapless transitions and 5-star session ratings.
- **Studio Coach Desk (`/grid` & `/coach`)** — Connect a laptop or Android tablet to your room's HDMI display: the coach controls classes, chapters, subtitles, and audio from the touch screen while members only see clean fullscreen video on the projector.
- **Smartphone Remote Control** — Open `http://bobine.local` from any phone on the studio Wi-Fi to pause, seek, switch subtitles, or launch a workout without installing an app.
- **24/7 Club Radio & Voice Reminders (`/radio`)** — Built-in music player with automatic crossfade, 5-band equalizer, playlists, and scheduled spoken announcements (e.g., *"Please re-rack your weights"*).
- **Two Independent Display & Radio Outputs** — Drive a wired HDMI screen and a secondary network screen simultaneously with separate content.
- **Attendance Metrics (`/metrics`)** — Track class completion rates, 5-star member feedback, peak studio hours, and device health locally.
- **15 Color Themes** — Light and dark high-contrast themes (including the Apple-inspired *Charbon* palette) adaptable to bright reception areas or dark cycling rooms.

---

## Quick Start

1. **Install and launch Bobine** on your computer, tablet, or mini PC.
2. **Open the interface** from any browser on the same Wi-Fi / Ethernet network:
   ```text
   http://bobine.local
   ```
   *(Or `http://127.0.0.1:1903` directly on the host machine).*
3. **Import your first videos or music tracks** by drag-and-drop in the **Library** tab, then launch a class or set up your weekly **Schedule**.

All web interfaces work out of the box on **Mozilla Firefox**, **Google Chrome**, **Microsoft Edge**, **Apple Safari**, **Brave**, and **Tor Browser** with zero client installation.

---

## Update Channels

Bobine offers three update channels, switchable anytime in **Settings → Software Updates**:

| Channel | Cadence | Who it is for | Links |
| :--- | :--- | :--- | :--- |
| **Stable** | Tagged version releases (`V5.0.7`) | Recommended default for production clubs and studios | [Latest Stable](https://github.com/FantasmaGlad/Bobine/releases/latest) |
| **Beta** | Curated preview batches | Early adopters wanting upcoming features before Stable | [Beta Release](https://github.com/FantasmaGlad/Bobine/releases/tag/beta) |
| **Canary** | Rebuilt on every commit to `main` | Power users and testers wanting the latest changes immediately | [Canary Release](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) |

---

## Documentation & Hardware Guides

- **User Guide & FAQ**: [bobine.fit/en/documentation](https://bobine.fit/en/documentation)
- **Independent Hardware Guide** *(mini PCs, tablets, TV boxes, HDMI adapters)*: [bobine.fit/en/hardware/aliexpress](https://bobine.fit/en/hardware/aliexpress)
- **Linux Package Portal** *(APT, DNF, Pacman instructions)*: [packages.bobine.fit](https://packages.bobine.fit)
- **Technical Architecture & API Reference**: [docs/ARCHITECTURE.en.md](docs/ARCHITECTURE.en.md)

---

## Security & License

- **Security**: Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/FantasmaGlad/Bobine/security/advisories/new) or [security@bobine.fit](mailto:security@bobine.fit) (OpenPGP fingerprint `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2`, details on [security.bobine.fit](https://security.bobine.fit) and [SECURITY.md](SECURITY.md)).
- **Contributing**: Bug reports and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- **License**: Free and open-source software licensed under the **GNU Affero General Public License v3.0 ([AGPL-3.0](LICENSE))**.

<sub>Related repositories: [BobineWeb](https://github.com/FantasmaGlad/BobineWeb) (website) · [bobine-packages](https://github.com/FantasmaGlad/bobine-packages) (Linux package repositories) · [homebrew-bobine](https://github.com/FantasmaGlad/homebrew-bobine) (Homebrew tap) · Security policy: [security.bobine.fit](https://security.bobine.fit), [`/.well-known/security.txt`](https://bobine.fit/.well-known/security.txt)</sub>
