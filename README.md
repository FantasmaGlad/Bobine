# Bobine

<p align="center">
  <img alt="Bobine" src="Assets/Images/LogoBanniere.png" width="100%">
</p>

<p align="center">
  <b>The open-source, self-hosted and 100% offline video playout, member kiosk, coach console, and 24/7 radio system for fitness clubs, gyms, and sports studios.</b>
</p>

<p align="center">
  <a href="https://bobine.fit"><b>Official Website</b></a> &nbsp;·&nbsp;
  <a href="#download"><b>Downloads</b></a> &nbsp;·&nbsp;
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

Group-fitness rooms and cycling studios play pre-recorded video classes on large screens or projectors. Proprietary systems charge a monthly subscription per screen, keep their catalog closed and need a permanent internet connection. Bobine does the same job as free software you install on your own hardware.

- **Your content, your hardware**: your videos, your schedule, your club branding. No account, no license fee.
- **Offline**: once installed, scheduled classes, the member kiosk and the radio run without internet.
- **One program, several screens**: weekly schedule, member kiosk (`/kiosk`, `/cinema`), coach desk (`/grid`, `/coach`), radio with spoken reminders (`/radio`), phone remote, attendance metrics.
- **Unattended**: starts on its own when powered on, including after a power cut.

## Download

Native application for computers, tablets, TVs and mini PCs. Stable 5.1.1 below; every channel and file on the [**releases page**](https://github.com/FantasmaGlad/Bobine/releases).

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

## Install from a terminal

Each command installs Stable. The Windows script checks the `SHA256SUMS` signature and the SHA-256 digest; Linux repositories are signed ([packages.bobine.fit](https://packages.bobine.fit)).

| System | Command |
| :--- | :--- |
| <img src="Assets/Icons/tools/powershell.svg" width="20" height="20" valign="middle" alt="PowerShell"> **Windows (PowerShell)** | `irm https://bobine.fit/install.ps1 \| iex` |
| <img src="Assets/Icons/tools/homebrew.svg" width="20" height="20" valign="middle" alt="Homebrew"> **macOS (Homebrew)** | `brew install --cask fantasmaglad/bobine/bobine` |
| <img src="Assets/Icons/os/linux.svg" width="20" height="20" valign="middle" alt="Linux"> **Linux (APT, DNF, pacman)** | see [packages.bobine.fit](https://packages.bobine.fit) |
| <img src="Assets/Icons/distros/debian.svg" width="20" height="20" valign="middle" alt="Debian"> **Mini PC (Debian 13)** | `curl -fsSL https://bobine.fit/install.sh \| bash` |

### Mini PC appliance

A mini PC under a minimal Debian 13 (x64 or ARM64, SSH enabled) becomes a dedicated player: it boots into the fullscreen kiosk on its HDMI screen. Install it from your computer with [Bobine Deploy](https://github.com/FantasmaGlad/bobine-deploy), which finds the mini PC on the network and installs over SSH, or run [`install.sh`](https://github.com/FantasmaGlad/Bobine/releases/download/V5.1.1/install.sh) on the mini PC itself (command above).

### Other channel, Tor

<details>
<summary><b>Another channel on Windows</b></summary>

The pipe does not forward parameters:

```powershell
$script = irm https://bobine.fit/install.ps1
& ([scriptblock]::Create($script)) -Channel beta
```

On Windows PowerShell 5.1 with a .NET runtime older than 4.7, run `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12` before `irm`.

</details>

<details>
<summary><img src="Assets/Icons/os/tor.svg" width="16" height="16" valign="middle" alt="Tor"> <b>Through Tor</b></summary>

GitHub and Homebrew then see a Tor exit instead of your address. The mini PC script is fetched from the onion mirror; the installation itself uses the regular network.

Windows (PowerShell 7.2+, Tor Browser open; `-TorPort 9050` for the tor service):

```powershell
$base = 'https://github.com/FantasmaGlad/Bobine/releases/latest/download'
$script = irm "$base/install.ps1" -Proxy socks5://127.0.0.1:9150
& ([scriptblock]::Create($script)) -Tor
```

macOS:

```bash
export ALL_PROXY=socks5h://127.0.0.1:9050
brew install --cask fantasmaglad/bobine/bobine
```

Linux repositories and signing key:

```bash
onion=http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion
curl --socks5-hostname 127.0.0.1:9050 -fsSL "$onion/install-tor.sh" | bash
```

Mini PC:

```bash
onion=http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion
curl --socks5-hostname 127.0.0.1:9050 -fsSL "$onion/install.sh" | bash
```

</details>

## Update channels

Three channels, switchable at any time in **Settings → Software Updates**.

| Channel | Published | For | Release |
| :--- | :--- | :--- | :--- |
| <img src="Assets/Images/Versions/Stable-cropped-1024.png" width="20" height="20" valign="middle" alt="Stable"> **Stable** | each tagged version (`V5.1.1`) | clubs and studios in production | [Stable](https://github.com/FantasmaGlad/Bobine/releases/latest) |
| <img src="Assets/Images/Versions/Beta-cropped-1024.png" width="20" height="20" valign="middle" alt="Beta"> **Beta** | batches chosen by the maintainer | trying upcoming features before Stable | [Beta](https://github.com/FantasmaGlad/Bobine/releases/tag/beta) |
| <img src="Assets/Images/Versions/Canary-cropped-1024.png" width="20" height="20" valign="middle" alt="Canary"> **Canary** | every commit on `main` | testing the latest changes | [Canary](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) |

## Documentation

| Subject | Where |
| :--- | :--- |
| User guide and FAQ | [bobine.fit/en/documentation](https://bobine.fit/en/documentation) |
| Author and project | [bobine.fit/en/about](https://bobine.fit/en/about) |
| Linux repositories | [packages.bobine.fit](https://packages.bobine.fit) |
| Architecture and API | [docs/ARCHITECTURE.en.md](docs/ARCHITECTURE.en.md) |

## Why go this far?

A weekly timetable of fitness classes does not need seven platforms, three update channels and a Tor mirror. These choices are deliberate; Bobine is also where its author practises them.

- **Every system and architecture**: so that "is it compatible?" is not a question. An old laptop, a tablet, a TV box, a second-hand mini PC: if the device sits in a garage, Bobine should install on it, whatever its power. Reusing a device avoids buying one.
- **Three update channels**: to run a clean release process, with Stable at the end of the line, Beta in chosen batches and Canary rebuilt on every change.
- **A Tor mirror**: out of proportion for a playout application. Publishing an application and its repositories through onion mirrors, without revealing the user's address, is a skill to master before publishing more sensitive software.
- **One person**: the whole chain, from source code to signed packages on each platform, is built and maintained by [Clément Barillot](https://bobine.fit/en/about).

## Security and license

- **Security**: report a vulnerability privately through [GitHub Security Advisories](https://github.com/FantasmaGlad/Bobine/security/advisories/new) or [security@bobine.fit](mailto:security@bobine.fit) (OpenPGP `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2`; details on [security.bobine.fit](https://security.bobine.fit) and in [SECURITY.md](SECURITY.md)).
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- **License**: [AGPL-3.0](LICENSE).

<sub>Related repositories: [bobine-deploy](https://github.com/FantasmaGlad/bobine-deploy) (remote installation) · [BobineWeb](https://github.com/FantasmaGlad/BobineWeb) (website) · [bobine-packages](https://github.com/FantasmaGlad/bobine-packages) (Linux repositories) · [homebrew-bobine](https://github.com/FantasmaGlad/homebrew-bobine) (Homebrew tap)</sub>
