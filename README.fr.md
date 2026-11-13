# Bobine

<p align="center">
  <img alt="Bobine" src="Assets/Images/LogoBanniere.png" width="100%">
</p>

<p align="center">
  <b>La régie vidéo open source, auto-hébergée et 100 % hors ligne pour salles de sport, studios de fitness et espaces de cours collectifs : cours planifiés, borne adhérents à la demande, pupitre coach et radio 24/7.</b>
</p>

<p align="center">
  <a href="https://bobine.fit/fr"><b>Site officiel</b></a> &nbsp;·&nbsp;
  <a href="#téléchargement"><b>Télécharger</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/fr/documentation"><b>Documentation utilisateur</b></a> &nbsp;·&nbsp;
  <a href="README.md"><b>English</b></a> &nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.md"><b>Architecture technique</b></a>
</p>

<p align="center">
  <a href="https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml"><img src="https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://github.com/FantasmaGlad/Bobine/releases/latest"><img src="https://img.shields.io/github/v/release/FantasmaGlad/Bobine?label=Stable&color=brightgreen" alt="Dernière version Stable"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/Licence-AGPL--3.0-blue.svg" alt="Licence : AGPL-3.0"></a>
  <img src="https://img.shields.io/badge/Architecture-100%25%20Hors%20ligne-success" alt="100% Hors ligne">
  <img src="https://img.shields.io/badge/Confidentialit%C3%A9-Z%C3%A9ro%20T%C3%A9l%C3%A9m%C3%A9trie-purple" alt="Zéro Télémétrie">
  <a href="https://packages.bobine.fit/fr/"><img src="https://img.shields.io/badge/D%C3%A9p%C3%B4ts%20Linux-packages.bobine.fit-A81D33?logo=linux&logoColor=white" alt="Dépôts Linux"></a>
</p>


---

## Pourquoi Bobine ?

Les salles de cours collectifs et les studios de cycling diffusent des cours vidéo enregistrés sur grand écran ou vidéoprojecteur. Les systèmes propriétaires facturent un abonnement mensuel par écran, gardent leur catalogue fermé et exigent une connexion internet permanente. Bobine fait le même travail en logiciel libre, installé sur votre propre matériel.

- **Vos contenus, votre matériel** : vos vidéos, votre planning, l'identité de votre club. Aucun compte, aucune redevance.
- **Hors ligne** : une fois installé, les cours planifiés, la borne adhérents et la radio fonctionnent sans internet.
- **Un programme, plusieurs écrans** : planning hebdomadaire, borne adhérents (`/kiosk`, `/cinema`), pupitre coach (`/grid`, `/coach`), radio avec rappels vocaux (`/radio`), télécommande sur téléphone, mesures de fréquentation.
- **Sans surveillance** : démarre seul à la mise sous tension, y compris après une coupure de courant.

## Téléchargement

Application native pour ordinateurs, tablettes, téléviseurs et mini PC. Version Stable 5.2.2 ci-dessous ; tous les canaux et fichiers sur la [**page des versions**](https://github.com/FantasmaGlad/Bobine/releases).

| Plateforme | Téléchargement | Prérequis |
| :--- | :--- | :--- |
| <img src="Assets/Icons/os/windows.svg" width="20" height="20" valign="middle" alt="Windows"> **Windows** 10 et 11 | [x64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/Bobine-Setup-5.2.2.exe) · [ARM64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/Bobine-Setup-5.2.2-arm64.exe) | installeur `.exe`, Snapdragon pris en charge |
| <img src="Assets/Icons/os/apple.svg" width="20" height="20" valign="middle" alt="macOS"> **macOS** | [Apple Silicon](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/Bobine-5.2.2.dmg) | M1 ou plus récent, `.dmg` |
| <img src="Assets/Icons/distros/debian.svg" width="20" height="20" valign="middle" alt="Debian"> **Debian, Ubuntu** | [APT](https://packages.bobine.fit/debian/) · [amd64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/bobine_5.2.2_amd64.deb) · [arm64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/bobine_5.2.2_arm64.deb) | glibc 2.38+ (Debian 13, Ubuntu 24.04) |
| <img src="Assets/Icons/distros/fedora.svg" width="20" height="20" valign="middle" alt="Fedora"> **Fedora, RHEL** | [DNF](https://packages.bobine.fit/fedora/) · [x86_64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/bobine-5.2.2-1.x86_64.rpm) · [aarch64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/bobine-5.2.2-1.aarch64.rpm) | glibc 2.38+ |
| <img src="Assets/Icons/distros/arch.svg" width="20" height="20" valign="middle" alt="Arch Linux"> **Arch Linux** | [pacman](https://packages.bobine.fit/arch/) · [x86_64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/bobine-5.2.2-1-x86_64.pkg.tar.zst) · [aarch64](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/bobine-5.2.2-1-aarch64.pkg.tar.zst) | glibc 2.38+ |
| <img src="Assets/Icons/os/android.svg" width="20" height="20" valign="middle" alt="Android"> **Android** | [APK](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/Bobine-5.2.2.apk) | Android 14+, ARM64 |
| <img src="Assets/Icons/os/androidtv.svg" width="20" height="20" valign="middle" alt="Android TV"> **Android TV, Google TV** | [APK TV](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/Bobine-TV-5.2.2.apk) | ARM 32 et 64 bits |
| <img src="Assets/Icons/os/tor.svg" width="20" height="20" valign="middle" alt="Tor"> **Tor (.onion)** | [site](http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/) · [paquets](http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/) | Tor Browser ou tor |

Mêmes paquets sur les dérivées (glibc 2.38+) : <img src="Assets/Icons/distros/linuxmint.svg" width="16" height="16" valign="middle" alt="Linux Mint" title="Linux Mint"> Linux Mint · <img src="Assets/Icons/distros/popos.svg" width="16" height="16" valign="middle" alt="Pop!_OS" title="Pop!_OS"> Pop!_OS · <img src="Assets/Icons/distros/zorin.svg" width="16" height="16" valign="middle" alt="Zorin OS" title="Zorin OS"> Zorin OS · <img src="Assets/Icons/distros/raspberrypi.svg" width="16" height="16" valign="middle" alt="Raspberry Pi OS" title="Raspberry Pi OS"> Raspberry Pi OS · <img src="Assets/Icons/distros/nobara.svg" width="16" height="16" valign="middle" alt="Nobara" title="Nobara"> Nobara · <img src="Assets/Icons/distros/rhel.svg" width="16" height="16" valign="middle" alt="RHEL" title="RHEL"> RHEL 10+ · <img src="Assets/Icons/distros/almalinux.svg" width="16" height="16" valign="middle" alt="AlmaLinux" title="AlmaLinux"> AlmaLinux 10+ · <img src="Assets/Icons/distros/rockylinux.svg" width="16" height="16" valign="middle" alt="Rocky Linux" title="Rocky Linux"> Rocky Linux 10+ · <img src="Assets/Icons/distros/endeavouros.svg" width="16" height="16" valign="middle" alt="EndeavourOS" title="EndeavourOS"> EndeavourOS · <img src="Assets/Icons/distros/cachyos.svg" width="16" height="16" valign="middle" alt="CachyOS" title="CachyOS"> CachyOS · <img src="Assets/Icons/distros/manjaro.svg" width="16" height="16" valign="middle" alt="Manjaro" title="Manjaro"> Manjaro

## Installer depuis un terminal

Chaque commande installe la version Stable. Le script Windows vérifie la signature de `SHA256SUMS` et l'empreinte SHA-256 ; les dépôts Linux sont signés ([packages.bobine.fit](https://packages.bobine.fit)).

| Système | Commande |
| :--- | :--- |
| <img src="Assets/Icons/tools/powershell.svg" width="20" height="20" valign="middle" alt="PowerShell"> **Windows (PowerShell)** | `irm https://bobine.fit/install.ps1 \| iex` |
| <img src="Assets/Icons/tools/homebrew.svg" width="20" height="20" valign="middle" alt="Homebrew"> **macOS (Homebrew)** | `brew install --cask fantasmaglad/bobine/bobine` |
| <img src="Assets/Icons/os/linux.svg" width="20" height="20" valign="middle" alt="Linux"> **Linux (APT, DNF, pacman)** | voir [packages.bobine.fit](https://packages.bobine.fit) |
| <img src="Assets/Icons/distros/debian.svg" width="20" height="20" valign="middle" alt="Debian"> **Mini PC (Debian 13)** | `curl -fsSL https://bobine.fit/install.sh \| bash` |

### Mini PC dédié

Un mini PC sous Debian 13 minimale (x64 ou ARM64, SSH activé) devient un lecteur dédié : il démarre sur la borne en plein écran sur sa sortie HDMI. Installez-le depuis votre ordinateur avec [Bobine Deploy](https://github.com/FantasmaGlad/bobine-deploy), qui trouve le mini PC sur le réseau et installe par SSH, ou lancez [`install.sh`](https://github.com/FantasmaGlad/Bobine/releases/download/V5.2.2/install.sh) sur le mini PC lui-même (commande ci-dessus).

### Autre canal, Tor

<details>
<summary><b>Un autre canal sous Windows</b></summary>

Le tube ne transmet pas de paramètre :

```powershell
$script = irm https://bobine.fit/install.ps1
& ([scriptblock]::Create($script)) -Channel beta
```

Sous Windows PowerShell 5.1 avec un .NET antérieur à 4.7, lancez `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12` avant `irm`.

</details>

<details>
<summary><img src="Assets/Icons/os/tor.svg" width="16" height="16" valign="middle" alt="Tor"> <b>Par Tor</b></summary>

GitHub et Homebrew voient alors une sortie Tor à la place de votre adresse. Le script du mini PC est lu sur le miroir onion ; l'installation elle-même passe par le réseau ordinaire.

Windows (PowerShell 7.2+, Tor Browser ouvert ; `-TorPort 9050` pour le service tor) :

```powershell
$base = 'https://github.com/FantasmaGlad/Bobine/releases/latest/download'
$script = irm "$base/install.ps1" -Proxy socks5://127.0.0.1:9150
& ([scriptblock]::Create($script)) -Tor
```

macOS :

```bash
export ALL_PROXY=socks5h://127.0.0.1:9050
brew install --cask fantasmaglad/bobine/bobine
```

Dépôts Linux et clé de signature :

```bash
onion=http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion
curl --socks5-hostname 127.0.0.1:9050 -fsSL "$onion/install-tor.sh" | bash
```

Mini PC :

```bash
onion=http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion
curl --socks5-hostname 127.0.0.1:9050 -fsSL "$onion/install.sh" | bash
```

</details>

## Canaux de mise à jour

Trois canaux, à changer à tout moment dans **Réglages → Mises à jour**.

| Canal | Publication | Pour | Version |
| :--- | :--- | :--- | :--- |
| <img src="Assets/Images/Versions/Stable-cropped-1024.png" width="20" height="20" valign="middle" alt="Stable"> **Stable** | chaque version taguée (`V5.2.2`) | les clubs et studios en exploitation | [Stable](https://github.com/FantasmaGlad/Bobine/releases/latest) |
| <img src="Assets/Images/Versions/Beta-cropped-1024.png" width="20" height="20" valign="middle" alt="Bêta"> **Bêta** | lots choisis par le mainteneur | essayer les nouveautés avant la Stable | [Bêta](https://github.com/FantasmaGlad/Bobine/releases/tag/beta) |
| <img src="Assets/Images/Versions/Canary-cropped-1024.png" width="20" height="20" valign="middle" alt="Canary"> **Canary** | chaque commit sur `main` | tester les derniers changements | [Canary](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) |

## Documentation

| Sujet | Où |
| :--- | :--- |
| Guide d'utilisation et FAQ | [bobine.fit/fr/documentation](https://bobine.fit/fr/documentation) |
| Auteur et projet | [bobine.fit/fr/a-propos](https://bobine.fit/fr/a-propos) |
| Dépôts Linux | [packages.bobine.fit](https://packages.bobine.fit/fr/) |
| Architecture et API | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |

## Pourquoi aller aussi loin ?

Un planning hebdomadaire de cours collectifs n'a pas besoin de sept plateformes, de trois canaux de mise à jour ni d'un miroir Tor. Ces choix sont voulus ; Bobine est aussi le terrain où son auteur les pratique.

- **Tous les systèmes et architectures** : pour que la question « est-ce compatible ? » ne se pose pas. Un ancien portable, une tablette, un boîtier TV, un mini PC d'occasion : si l'appareil dort dans un garage, Bobine doit pouvoir s'y installer, quelle que soit sa puissance. Réutiliser un appareil évite d'en acheter un.
- **Trois canaux de mise à jour** : pour tenir un processus de diffusion propre, avec la Stable en bout de chaîne, la Bêta par lots choisis et la Canary reconstruite à chaque modification.
- **Un miroir Tor** : disproportionné pour une application de régie. Publier une application et ses dépôts par des miroirs onion, sans révéler l'adresse de l'utilisateur, est un savoir-faire à maîtriser avant de publier des logiciels plus sensibles.
- **Une seule personne** : toute la chaîne, du code source aux paquets signés de chaque plateforme, est construite et maintenue par [Clément Barillot](https://bobine.fit/fr/a-propos).

## Sécurité et licence

- **Sécurité** : signalez une vulnérabilité en privé par [GitHub Security Advisories](https://github.com/FantasmaGlad/Bobine/security/advisories/new) ou à [security@bobine.fit](mailto:security@bobine.fit) (OpenPGP `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2` ; détails sur [security.bobine.fit](https://security.bobine.fit/fr/) et dans [SECURITY.md](SECURITY.md)).
- **Contribuer** : [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- **Licence** : [AGPL-3.0](LICENSE).

<sub>Dépôts liés : [bobine-deploy](https://github.com/FantasmaGlad/bobine-deploy) (installation à distance) · [BobineWeb](https://github.com/FantasmaGlad/BobineWeb) (site) · [bobine-packages](https://github.com/FantasmaGlad/bobine-packages) (dépôts Linux) · [homebrew-bobine](https://github.com/FantasmaGlad/homebrew-bobine) (tap Homebrew)</sub>
