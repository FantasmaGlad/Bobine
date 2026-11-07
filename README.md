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

Native application for computers, tablets, TVs and mini PCs. Stable 5.1.1 below; every channel and file on [**bobine.fit/en/download**](https://bobine.fit/en/download).

| Platform | Download | Requirements |
| :--- | :--- | :--- |
| <img src="Assets/Icons/os/windows.svg" width="20" height="20" valign="middle" alt="Windows"> **Windows** 10 & 11 | [x64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/Bobine-Setup-5.1.1.exe) · [ARM64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/Bobine-Setup-5.1.1-arm64.exe) | `.exe` installer, Snapdragon supported |
| <img src="Assets/Icons/os/apple.svg" width="20" height="20" valign="middle" alt="macOS"> **macOS** | [Apple Silicon](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/Bobine-5.1.1.dmg) | M1 or newer, `.dmg` |
| <img src="Assets/Icons/distros/debian.svg" width="20" height="20" valign="middle" alt="Debian"> **Debian, Ubuntu** | [APT](https://packages.bobine.fit/debian/) · [amd64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/bobine_5.1.1_amd64.deb) · [arm64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/bobine_5.1.1_arm64.deb) | glibc 2.38+ (Debian 13, Ubuntu 24.04) |
| <img src="Assets/Icons/distros/fedora.svg" width="20" height="20" valign="middle" alt="Fedora"> **Fedora, RHEL** | [DNF](https://packages.bobine.fit/fedora/) · [x86_64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/bobine-5.1.1-1.x86_64.rpm) · [aarch64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/bobine-5.1.1-1.aarch64.rpm) | glibc 2.38+ |
| <img src="Assets/Icons/distros/arch.svg" width="20" height="20" valign="middle" alt="Arch Linux"> **Arch Linux** | [pacman](https://packages.bobine.fit/arch/) · [x86_64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/bobine-5.1.1-1-x86_64.pkg.tar.zst) · [aarch64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/bobine-5.1.1-1-aarch64.pkg.tar.zst) | glibc 2.38+ |
| <img src="Assets/Icons/os/android.svg" width="20" height="20" valign="middle" alt="Android"> **Android** | [APK](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/Bobine-5.1.1.apk) | Android 14+, ARM64 |
| <img src="Assets/Icons/os/androidtv.svg" width="20" height="20" valign="middle" alt="Android TV"> **Android TV, Google TV** | [APK TV](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/Bobine-TV-5.1.1.apk) | ARM 32 and 64-bit |
| <img src="Assets/Icons/os/tor.svg" width="20" height="20" valign="middle" alt="Tor"> **Tor (.onion)** | [website](http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/) · [packages](http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/) | Tor Browser or tor |

Same packages on derivatives (glibc 2.38+): <img src="Assets/Icons/distros/linuxmint.svg" width="16" height="16" valign="middle" alt="Linux Mint" title="Linux Mint"> Linux Mint · <img src="Assets/Icons/distros/popos.svg" width="16" height="16" valign="middle" alt="Pop!_OS" title="Pop!_OS"> Pop!_OS · <img src="Assets/Icons/distros/zorin.svg" width="16" height="16" valign="middle" alt="Zorin OS" title="Zorin OS"> Zorin OS · <img src="Assets/Icons/distros/raspberrypi.svg" width="16" height="16" valign="middle" alt="Raspberry Pi OS" title="Raspberry Pi OS"> Raspberry Pi OS · <img src="Assets/Icons/distros/nobara.svg" width="16" height="16" valign="middle" alt="Nobara" title="Nobara"> Nobara · <img src="Assets/Icons/distros/rhel.svg" width="16" height="16" valign="middle" alt="RHEL" title="RHEL"> RHEL 10+ · <img src="Assets/Icons/distros/almalinux.svg" width="16" height="16" valign="middle" alt="AlmaLinux" title="AlmaLinux"> AlmaLinux 10+ · <img src="Assets/Icons/distros/rockylinux.svg" width="16" height="16" valign="middle" alt="Rocky Linux" title="Rocky Linux"> Rocky Linux 10+ · <img src="Assets/Icons/distros/endeavouros.svg" width="16" height="16" valign="middle" alt="EndeavourOS" title="EndeavourOS"> EndeavourOS · <img src="Assets/Icons/distros/cachyos.svg" width="16" height="16" valign="middle" alt="CachyOS" title="CachyOS"> CachyOS · <img src="Assets/Icons/distros/manjaro.svg" width="16" height="16" valign="middle" alt="Manjaro" title="Manjaro"> Manjaro

### Mini PC appliance

Turns a mini PC (Debian 13, x64 or ARM64) into a dedicated Bobine player: it starts straight into the fullscreen kiosk on its HDMI screen and resumes on its own after a power cut.

- **From your computer, with [Bobine Deploy](https://github.com/FantasmaGlad/bobine-deploy)**: it finds the mini PC on your network, connects to it over SSH and installs everything with a progress bar, from a window or the command line (Linux, Windows, macOS; [releases](https://github.com/FantasmaGlad/bobine-deploy/releases/latest)).
- **Directly on the mini PC**, in a terminal ([install.sh](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/install.sh)):

  ```bash
  curl -fsSL https://bobine.fit/install.sh | bash
  ```

- **Script fetched through Tor** from the onion mirror (the installation itself then uses the regular network):

  ```bash
  onion=http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion
  curl --socks5-hostname 127.0.0.1:9050 -fsSL "$onion/install.sh" | bash
  ```

Requirements: minimal Debian 13 install with SSH enabled, on the same network as your computer.

### One-command install

<img src="Assets/Icons/tools/powershell.svg" width="20" height="20" alt="PowerShell"> Windows (PowerShell): installs Stable after checking the `SHA256SUMS` signature and its SHA-256 digest, without gpg.

```powershell
irm https://bobine.fit/install.ps1 | iex
```

On Windows PowerShell 5.1 with a .NET runtime older than 4.7, run `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12` before `irm`; the script cannot change the TLS version of the request that downloads it.

Another channel (the pipe does not forward parameters):

```powershell
& ([scriptblock]::Create((irm https://bobine.fit/install.ps1))) -Channel beta
```

Through Tor (PowerShell 7.2+, Tor Browser open; `-TorPort 9050` for the tor service):

```powershell
$u = 'https://github.com/FantasmaGlad/Bobine/releases/latest/download/install.ps1'
$script = irm $u -Proxy socks5://127.0.0.1:9150
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
onion=http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion
curl --socks5-hostname 127.0.0.1:9050 -fsSL "$onion/install-tor.sh" | bash
```

<img src="Assets/Icons/os/tor.svg" width="20" height="20" alt="Tor"> Through Tor, GitHub and Homebrew see a Tor exit instead of your address.

---

## Key Features

- **Weekly Class Timetable** — Schedule your group classes across the week; workouts start automatically on time on the right screen.
- **Interactive Member Kiosk (`/kiosk` & `/cinema`)** — Let members browse your catalog by category and start a class on demand using a touch screen, TV remote, gamepad, or mouse, with gapless transitions and 5-star session ratings.
- **Studio Coach Desk (`/grid` & `/coach`)** — Connect a laptop or Android tablet to your room's HDMI display: the coach controls classes, chapters, subtitles, and audio from the touch screen while members only see clean fullscreen video on the projector.
- **Smartphone Remote Control** — Open `http://bobine.local:1903` from any phone on the studio Wi-Fi to pause, seek, switch subtitles, or launch a workout without installing an app.
- **24/7 Club Radio & Voice Reminders (`/radio`)** — Built-in music player with automatic crossfade, 5-band equalizer, playlists, and scheduled spoken announcements (e.g., *"Please re-rack your weights"*).
- **Two Independent Display & Radio Outputs** — Drive a wired HDMI screen and a secondary network screen simultaneously with separate content.
- **Attendance Metrics (`/metrics`)** — Track class completion rates, 5-star member feedback, peak studio hours, and device health locally.
- **9 Color Themes, each in light and dark** — automatic mode following the device, verified contrast, no gradient in the backgrounds; adaptable to bright reception areas or dark cycling rooms.

---

## Quick Start

1. **Install and launch Bobine** on your computer, tablet, or mini PC.
2. **Open the interface** from any browser on the same Wi-Fi / Ethernet network:
   ```text
   http://bobine.local:1903
   ```
   *(Or `http://127.0.0.1:1903` directly on the host machine; without the port on the mini PC appliance. Every address of the device is listed in Settings → Documentation.)*
3. **Import your first videos** by drag-and-drop in the **Library** tab (music goes in the **Radio Audio Tracks** tab), then launch a class or set up your weekly **Schedule**.

All web interfaces work out of the box on **Mozilla Firefox**, **Google Chrome**, **Microsoft Edge**, **Apple Safari**, **Brave**, and **Tor Browser** with zero client installation.

---

## Update Channels

Bobine offers three update channels, switchable anytime in **Settings → Software Updates**:

| Channel | Cadence | Who it is for | Links |
| :--- | :--- | :--- | :--- |
| **Stable** | Tagged version releases (`V5.1.1`) | Recommended default for production clubs and studios | [Latest Stable](https://github.com/FantasmaGlad/Bobine/releases/latest) |
| **Beta** | Curated preview batches | Early adopters wanting upcoming features before Stable | [Beta Release](https://github.com/FantasmaGlad/Bobine/releases/tag/beta) |
| **Canary** | Rebuilt on every commit to `main` | Power users and testers wanting the latest changes immediately | [Canary Release](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) |

---

## Documentation & Hardware Guides

- **User Guide & FAQ**: [bobine.fit/en/documentation](https://bobine.fit/en/documentation)
- **Hardware Compatibility** *(mini PCs, laptops, tablets, TV boxes)*: [bobine.fit/en/download](https://bobine.fit/en/download)
- **Linux Package Portal** *(APT, DNF, Pacman instructions)*: [packages.bobine.fit](https://packages.bobine.fit)
- **Technical Architecture & API Reference**: [docs/ARCHITECTURE.en.md](docs/ARCHITECTURE.en.md)

---

## Security & License

- **Security**: Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/FantasmaGlad/Bobine/security/advisories/new) or [security@bobine.fit](mailto:security@bobine.fit) (OpenPGP fingerprint `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2`, details on [security.bobine.fit](https://security.bobine.fit) and [SECURITY.md](SECURITY.md)).
- **Contributing**: Bug reports and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- **License**: Free and open-source software licensed under the **GNU Affero General Public License v3.0 ([AGPL-3.0](LICENSE))**.

<sub>Related repositories: [bobine-deploy](https://github.com/FantasmaGlad/bobine-deploy) (remote installation) · [BobineWeb](https://github.com/FantasmaGlad/BobineWeb) (website) · [bobine-packages](https://github.com/FantasmaGlad/bobine-packages) (Linux package repositories) · [homebrew-bobine](https://github.com/FantasmaGlad/homebrew-bobine) (Homebrew tap) · Security policy: [security.bobine.fit](https://security.bobine.fit), [`/.well-known/security.txt`](https://bobine.fit/.well-known/security.txt)</sub>
