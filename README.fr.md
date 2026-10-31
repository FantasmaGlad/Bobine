# Bobine

<p align="center">
  <img alt="Bobine" src="Assets/Images/LogoBanniere.png" width="100%">
</p>

<p align="center">
  <b>La régie vidéo open source, auto-hébergée et 100 % hors ligne pour salles de sport, studios de fitness et espaces de cours collectifs : cours planifiés, borne adhérents à la demande, pupitre coach et radio 24/7.</b>
</p>

<p align="center">
  <a href="https://bobine.fit/fr"><b>Site officiel</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/fr/telechargement"><b>Télécharger</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/fr/documentation"><b>Documentation utilisateur</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/fr/materiel/aliexpress"><b>Matériel recommandé</b></a> &nbsp;·&nbsp;
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

Les salles de cours collectifs et studios de cycling diffusent quotidiennement des cours vidéo sur grand écran ou vidéoprojecteur. Les solutions propriétaires comme Les Mills Cinema, Wexer Virtual ou Fitness On Demand imposent des abonnements mensuels par écran, un catalogue fermé et une connexion internet permanente.

**Bobine offre la même expérience en salle — gratuitement, sans abonnement et en toute autonomie :**

- **Vous êtes propriétaire** — vos vidéos, votre planning, l'identité visuelle de votre club et votre matériel. Aucun compte requis, aucune redevance mensuelle.
- **100 % hors ligne** — une fois installé, la salle n'a besoin d'aucune connexion internet pour lancer les cours planifiés, la borne adhérents ou la radio d'ambiance.
- **Compatible avec votre matériel** — s'installe en quelques secondes sur Windows, macOS, Linux, tablette Android, Google Book, boîtier Android TV ou mini PC dédié.
- **Autonome 24/7** — démarre tout seul à la mise sous tension et reprend automatiquement la séance en cours après une coupure de courant.

---

## Téléchargement & Installation

Choisissez l'application correspondant à votre appareil (ou rendez-vous sur [**bobine.fit/fr/telechargement**](https://bobine.fit/fr/telechargement)) :

| Plateforme | Téléchargement direct / Commande | Usage type en club |
| :--- | :--- | :--- |
| <img src="Assets/Icons/os/windows.svg" width="18" height="18" valign="middle" alt="Windows"> **Windows 11 & 10** | [**Bobine-Setup-5.0.7.exe (x86-64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-Setup-5.0.7.exe)<br>[**Bobine-Setup-5.0.7-arm64.exe (ARM64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-Setup-5.0.7-arm64.exe) | PC fixe ou portable relié en HDMI au téléviseur ou vidéoprojecteur de la salle |
| <img src="Assets/Icons/os/apple.svg" width="18" height="18" valign="middle" alt="macOS"> **macOS** *(Apple Silicon)* | [**Bobine-5.0.7.dmg**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-5.0.7.dmg) | MacBook Air, MacBook Pro, Mac mini ou iMac (M1–M4) |
| <img src="Assets/Icons/os/linux.svg" width="18" height="18" valign="middle" alt="Linux"> **Linux Bureau** | [**packages.bobine.fit**](https://packages.bobine.fit/fr/) *(APT, DNF, Pacman)*<br>[**`.deb` amd64**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine_5.0.7_amd64.deb) · [**`.deb` arm64**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine_5.0.7_arm64.deb) · [**`.rpm`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-5.0.7-1.x86_64.rpm) · [**Arch**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-5.0.7-1-x86_64.pkg.tar.zst) | Debian 13+, Ubuntu 24.04+, Linux Mint, Fedora, Arch Linux (`x86_64` et `arm64`, exige glibc 2.38 ou plus récente) |
| <img src="Assets/Icons/os/android.svg" width="18" height="18" valign="middle" alt="Android"> **Android & Google Book** | [**Bobine-5.0.7.apk**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-5.0.7.apk) | Pupitre coach tactile sur la tablette + diffusion cinéma plein écran en HDMI |
| <img src="Assets/Icons/os/androidtv.svg" width="18" height="18" valign="middle" alt="Android TV"> **Android TV & Google TV** | [**Bobine-TV-5.0.7.apk**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/Bobine-TV-5.0.7.apk) | Diffusion directe sur téléviseur pilotée avec la télécommande d'origine |
| <img src="Assets/Images/bash.svg" width="18" height="18" valign="middle" alt="Appliance"> **Mini PC dédié** *(Debian 13)* | `curl -fsSL https://bobine.fit/install.sh \| bash` | Borne autonome 24/7 (ou déploiement graphique via [**bobine-assistant**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.7/bobine-assistant)) |
| <img src="Assets/Icons/os/tor.svg" width="18" height="18" valign="middle" alt="Tor"> **Réseau Tor (.onion)** | `curl -fsSL https://bobine.fit/install-tor.sh \| bash`<br>[**Miroir Tor**](http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/) · [**Dépôt APT .onion**](http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/) | Installation et mises à jour anonymes sans exposer l'adresse IP de la salle |

---

## Fonctionnalités clés

- **Planning hebdomadaire automatisé** — Programmez la grille horaire de vos salles ; les cours démarrent automatiquement à l'heure prévue sur le bon écran.
- **Borne adhérents à la demande (`/kiosk` & `/cinema`)** — Permettez aux membres de parcourir le catalogue par discipline et de lancer une séance en libre-service (écran tactile, télécommande TV, manette ou souris), avec enchaînement fluide sans écran noir et notation sur 5 étoiles en fin de séance.
- **Pupitre Studio Coach (`/grid` & `/coach`)** — Reliez un ordinateur portable ou une tablette Android en HDMI à l'écran de la salle : l'écran tactile sert de console de pilotage (sélection, chapitres, sous-titres, mode audio coach) tandis que le grand écran diffuse uniquement le cours en plein écran.
- **Télécommande mobile par QR code** — Scannez un QR code local depuis n'importe quel smartphone connecté au Wi-Fi du club pour mettre en pause, avancer, choisir les sous-titres ou lancer un cours sans installer d'application.
- **Radio d'ambiance 24/7 & Rappels vocaux (`/radio`)** — Lecteur musical continu avec fondu enchaîné, égaliseur 5 bandes, playlists et diffusion automatique d'annonces vocales programmées (*« Pensez à ranger vos poids »*, etc.).
- **Deux sorties d'écran et de radio indépendantes** — Pilotez simultanément un écran câblé (HDMI) et un écran réseau avec deux programmes distincts.
- **Statistiques de fréquentation (`/metrics`)** — Suivez en local l'assiduité des cours, les notes des adhérents, les heures d'affluence sur 24 h et l'état du matériel.
- **16 thèmes de couleurs** — Thèmes clairs et sombres à fort contraste (dont le thème *Charbon* inspiré d'Apple) adaptés aux espaces d'accueil lumineux comme aux salles de cycling immersives.

---

## Prise en main rapide

1. **Installez et lancez Bobine** sur votre ordinateur, tablette ou mini PC.
2. **Ouvrez l'interface** depuis n'importe quel navigateur connecté au même réseau Wi-Fi ou Ethernet :
   ```text
   http://bobine.local
   ```
   *(Ou `http://127.0.0.1:8000` directement sur la machine hôte).*
3. **Importez vos premières vidéos ou musiques** par glisser-déposer dans l'onglet **Bibliothèque**, puis lancez une séance ou configurez votre **Planning**.

Toutes les interfaces fonctionnent immédiatement sur **Mozilla Firefox**, **Google Chrome**, **Microsoft Edge**, **Apple Safari**, **Brave** et **Tor Browser**, sans aucune installation sur les appareils clients.

---

## Canaux de mise à jour

Bobine propose trois canaux de mise à jour, modifiables à tout moment dans **Réglages → Mises à jour logicielles** :

| Canal | Cadence | Public visé | Liens |
| :--- | :--- | :--- | :--- |
| **Stable** | Versions officielles taguées (`V5.0.7`) | Choix par défaut recommandé pour l'exploitation en salle | [Dernière Stable](https://github.com/FantasmaGlad/Bobine/releases/latest) |
| **Bêta** | Lots d'accès anticipé sélectionnés | Découverte des prochaines nouveautés avant leur sortie Stable | [Release Bêta](https://github.com/FantasmaGlad/Bobine/releases/tag/beta) |
| **Canary** | Reconstruite à chaque commit sur `main` | Utilisateurs avancés souhaitant tester immédiatement les derniers changements | [Release Canary](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) |

---

## Documentation & Guides matériel

- **Guide utilisateur & FAQ** : [bobine.fit/fr/documentation](https://bobine.fit/fr/documentation)
- **Sélection matérielle indépendante** *(mini PC, tablettes, box TV, adaptateurs HDMI)* : [bobine.fit/fr/materiel/aliexpress](https://bobine.fit/fr/materiel/aliexpress)
- **Portail des paquets Linux** *(instructions APT, DNF, Pacman)* : [packages.bobine.fit/fr/](https://packages.bobine.fit/fr/)
- **Architecture technique & Référence API** : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Sécurité & Licence

- **Sécurité** : Signalez toute vulnérabilité en privé via [GitHub Security Advisories](https://github.com/FantasmaGlad/Bobine/security/advisories/new) ou à [security@bobine.fit](mailto:security@bobine.fit) (empreinte OpenPGP `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2`, détails sur [security.bobine.fit/fr/](https://security.bobine.fit/fr/) et [docs/fr/SECURITY.md](docs/fr/SECURITY.md)).
- **Contribuer** : Les signalements de bugs et contributions sont bienvenus — voir [docs/fr/CONTRIBUTING.md](docs/fr/CONTRIBUTING.md) et [docs/fr/CODE_OF_CONDUCT.md](docs/fr/CODE_OF_CONDUCT.md).
- **Licence** : Logiciel libre et gratuit distribué sous licence **GNU Affero General Public License v3.0 ([AGPL-3.0](LICENSE))**.
