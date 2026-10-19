# Bobine

<p align="center">
  <img alt="Bobine" src="Assets/Images/LogoBanniere.png" width="100%">
</p>

<table align="center">
  <tr>
    <td align="center" valign="middle"><img alt="Google Book compatible avec Bobine" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/googlebooks.webp" width="400"></td>
    <td align="center" valign="middle"><img alt="Bobine soutient Firefox — le renard Firefox et Baamix, la mascotte de Bobine" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/FirefoxBaamix.png" width="400"></td>
  </tr>
</table>

<p align="center">
  <b>Ajout récent — Bobine soutient officiellement Firefox & l'architecture ARM64.</b><br>
  <sub>Écosystème ARM64 natif (PC portables Snapdragon X, Linux ARM64, NVIDIA DGX Spark, Google Books), système à trois canaux (Stable/Bêta/Canary) et validation Firefox 157. <a href="#navigateurs-supportés">Navigateurs supportés</a></sub>
</p>

<p align="center">
  <a href="https://bobine.fit"><b>Site officiel</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/fr/materiel"><b>Recommandations matérielles</b></a> &nbsp;·&nbsp;
  <a href="https://bobine.fit/fr/documentation"><b>Documentation web</b></a> &nbsp;·&nbsp;
  <a href="README.md"><b>English</b></a> &nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.md"><b>Documentation technique</b></a><br>
  <a href="https://github.com/FantasmaGlad/Bobine/releases/latest"><b>Dernière version (v5.0.0)</b></a> &nbsp;·&nbsp;
  <a href="https://github.com/FantasmaGlad/Bobine/releases/tag/beta"><b>Release Bêta</b></a> &nbsp;·&nbsp;
  <a href="https://github.com/FantasmaGlad/Bobine/releases/tag/canary"><b>Release Canary</b></a>
</p>

<p align="center">
  <a href="https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml"><img src="https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://github.com/FantasmaGlad/Bobine/releases/latest"><img src="https://img.shields.io/badge/Release-v5.0.0-brightgreen" alt="Version : v5.0.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-blue.svg" alt="Licence : AGPL-3.0"></a>
  <img src="https://img.shields.io/badge/Architecture-Local--first%20%7C%20100%25%20Hors--ligne-success" alt="Architecture">
  <img src="https://img.shields.io/badge/Confidentialit%C3%A9-Z%C3%A9ro%20T%C3%A9l%C3%A9m%C3%A9trie-purple" alt="Confidentialité">
  <img src="https://img.shields.io/badge/Vid%C3%A9o-4K%2060fps%20Natif-orange" alt="Vidéo">
  <img src="https://img.shields.io/badge/Acc%C3%A9l%C3%A9ration%20mat%C3%A9rielle-VA--API%20%7C%20VideoToolbox%20%7C%20MediaCodec%20%7C%20QSV-red" alt="Accélération matérielle">
  <img src="https://img.shields.io/badge/Navigateurs-Firefox%20%7C%20Chrome%20%7C%20Edge%20%7C%20Safari-FF7139?logo=firefoxbrowser&logoColor=white" alt="Navigateurs">
  <a href="https://apt.bobine.fit"><img src="https://img.shields.io/badge/D%C3%A9p%C3%B4t%20APT-apt.bobine.fit-A81D33?logo=debian&logoColor=white" alt="Dépôt APT"></a>
  <a href="https://github.com/FantasmaGlad/Bobine/pulls"><img src="https://img.shields.io/badge/PRs-bienvenues-brightgreen.svg" alt="Contributions bienvenues"></a>
</p>

---

## Téléchargement rapide & Applications natives

Installez Bobine en quelques secondes comme une application autonome sur votre tablette tactile, poste de travail ou PC de régie studio :

| Plateforme | Format | Architecture | Téléchargement direct / Commande | Profil & Fonctionnalités Clés |
| :--- | :---: | :---: | :---: | :--- |
| ![](https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white) | <sub>`.apk`<br>*(Paquet natif)*</sub> | <sub>ARM64<br>*(arm64-v8a)*</sub> | <sub>[**Télécharger Bobine-5.0.0.apk**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.apk)</sub> | **Tablettes Android & Google Books (Aluminium OS)**<br><sub>Pupitre coach tactile (`/grid`) + grand écran HDMI (`/cinema`), bientôt sur Google Play Store</sub> |
| ![](https://img.shields.io/badge/Android_TV-009688?style=flat-square&logo=android&logoColor=white) | <sub>`.apk`<br>*(Paquet TV dédié)*</sub> | <sub>ARM 32 & 64 bits<br>*(armeabi-v7a, arm64-v8a)*</sub> | <sub>[**Télécharger Bobine-TV-5.0.0.apk**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-TV-5.0.0.apk)</sub> | **Android TV & Google TV**<br><sub>Bannière Leanback TV, navigation télécommande D-Pad, mode autonome</sub> |
| ![](https://img.shields.io/badge/Windows_11-0078D4?style=flat-square&logo=windows11&logoColor=white) | <sub>`.exe`<br>*(Installeur)*</sub> | <sub>x86-64 & ARM64<br>*(Snapdragon)*</sub> | <sub>[**Bobine-Setup-5.0.0.exe (x86-64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-Setup-5.0.0.exe)<br>[**Bobine-Setup-5.0.0-arm64.exe (ARM64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-Setup-5.0.0-arm64.exe)</sub> | **PC Windows 11/10 & Portables ARM Qualcomm Snapdragon**<br><sub>Installeur natif x86-64 et ARM64 (Snapdragon X Elite / X Plus), systray, mode clamshell</sub> |
| ![](https://img.shields.io/badge/Debian-A81D33?style=flat-square&logo=debian&logoColor=white) ![](https://img.shields.io/badge/Ubuntu-E95420?style=flat-square&logo=ubuntu&logoColor=white) ![](https://img.shields.io/badge/Linux%20Mint-87CF3E?style=flat-square&logo=linuxmint&logoColor=white) | <sub>`.deb`<br>*(Paquet & Dépôt)*</sub> | <sub>x86-64 *(amd64)*<br>& ARM64 *(arm64)*</sub> | <sub>[**Dépôt APT apt.bobine.fit**](https://apt.bobine.fit)<br>[**bobine_5.0.0_amd64.deb**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine_5.0.0_amd64.deb)<br>[**bobine_5.0.0_arm64.deb**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine_5.0.0_arm64.deb)</sub> | **Postes Linux, Stations ARM64 & NVIDIA DGX Spark**<br><sub>Paquets `.deb` officiels (`amd64` & `arm64`) et dépôt `apt.bobine.fit`</sub> |
| ![](https://img.shields.io/badge/macOS-000000?style=flat-square&logo=apple&logoColor=white) | <sub>`.dmg`<br>*(Image disque)*</sub> | <sub>Apple Silicon<br>*(arm64)*</sub> | <sub>[**Télécharger Bobine-5.0.0.dmg**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.dmg)</sub> | **MacBook, Mac mini & iMac**<br><sub>Glisser-déposer `.dmg`, Apple Silicon & Intel, barre de menus</sub> |
| ![](https://img.shields.io/badge/iOS%20%2F%20iPadOS-000000?style=flat-square&logo=apple&logoColor=white) | <sub>App iPadOS<br>*(Piste explorée)*</sub> | <sub>ARM64 (Apple Silicon)</sub> | <sub>*Piste explorée...*</sub> | **iPads & Tablettes Apple (Piste explorée)**<br><sub>Prototype pupitre coach avec sortie vidéo USB-C / Thunderbolt</sub> |
| ![](https://img.shields.io/badge/Bobine_Assistant-FFC131?style=flat-square&logo=tauri&logoColor=black) | <sub>Binaire natif<br>*(Tauri 2)*</sub> | <sub>x86-64 & ARM64<br>*(Linux)*</sub> | <sub>[**bobine-assistant (x86-64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine-assistant)<br>[**bobine-assistant-arm64 (ARM64)**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine-assistant-arm64)</sub> | **Assistant Graphique de Déploiement**<br><sub>Découverte réseau locale, audit matériel et déploiement SSH</sub> |
| ![](https://img.shields.io/badge/Bash_CLI-4EAA25?style=flat-square&logo=gnubash&logoColor=white) | <sub>Script Shell<br>*(Automatisé)*</sub> | <sub>x86-64 & ARM64</sub> | <sub>`curl -sSL https://bobine.fit/install.sh \| bash`</sub> | **Appliance Dédiée Headless (x86-64 & ARM64)**<br><sub>Installation automatisée en 18 étapes sur mini-PC et stations ARM64 (Debian 13)</sub> |
| [![](https://img.shields.io/badge/Tor_Browser-7D4698?style=flat-square&logo=torbrowser&logoColor=white)](http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/) | <sub>Dépôt APT & Miroir<br>*(Réseau Tor)*</sub> | <sub>x86-64 & ARM64<br>*(amd64 / arm64)*</sub> | <sub>`curl -fsSL https://bobine.fit/install-tor.sh \| bash`<br>[**Site miroir .onion**](http://bobinedaoki42tt33rxacmtaab2gxvxb2orqgcyhvowv3aggxhruvrid.onion/)<br>[**Dépôt APT .onion**](http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/)</sub> | **Distribution Tor (.onion)**<br><sub>Dépôt APT et miroir anonymes sans exposition d'adresse IP</sub> |
| [![](https://img.shields.io/badge/bobine.fit-4285F4?style=flat-square&logo=data%3Aimage/svg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0OCA0OCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4Ij48cGF0aCBmaWxsPSIjNENBRjUwIiBkPSJNNDQgMjRjMCAxMS4wNDUtOC45NTUgMjAtMjAgMjAtNC41MiAwLTguNjgtMS41MDMtMTIuMDMtNC4wNDNsOS40NjctMTYuMzk0QTggOCAwIDAgMCAyNCAzMmM0LjQxOCAwIDgtMy41ODIgOC04eiIvPjxwYXRoIGZpbGw9IiNGQkMwMkQiIGQ9Ik00NCAyNEgyNGE4IDggMCAwIDAtNi45MjggNGwtOS40NjcgMTYuMzk0QTE5LjkyIDE5LjkyIDAgMCAxIDQgMjRDNCAxMy45ODcgMTEuMzg1IDUuNzA0IDIxLjAzNiA0LjIyTDMwLjUwMyAyMC42MUE3Ljk3IDcuOTcgMCAwIDAgMzIgMjR6Ii8%2BPHBhdGggZmlsbD0iI0U1MzkzNSIgZD0iTTI0IDRjNy40MDYgMCAxMy44NiA0LjAyNCAxNy4zIDEwLjAyN0wzMC41MDMgMjAuNjFBOCA4IDAgMCAwIDI0IDE2Yy0zLjE1NSAwLTUuOTE0IDEuODI2LTcuMjUgNC40OUw3LjI4NCA0LjA5NUMxMS44OTIgNC4wMzIgMTcuNjUgNCAyNCA0eiIvPjxjaXJjbGUgY3g9IjI0IiBjeT0iMjQiIHI9IjgiIGZpbGw9IiNGRkYiLz48Y2lyY2xlIGN4PSIyNCIgY3k9IjI0IiByPSI2IiBmaWxsPSIjMTk3NkQyIi8%2BPC9zdmc%2B)](https://bobine.fit) | <sub>Portail Web</sub> | <sub>Universel</sub> | <sub>[**Visiter bobine.fit**](https://bobine.fit)</sub> | **Site Officiel & Documentation**<br><sub>Guides de prise en main, conseils matériel et base de connaissances</sub> |
| ![](https://img.shields.io/badge/GitHub-Releases-181717?style=flat-square&logo=github&logoColor=white) | <sub>Binaires & Sources</sub> | <sub>Multi-OS</sub> | <sub>[**Voir les Releases GitHub**](https://github.com/FantasmaGlad/Bobine/releases/latest)</sub> | **Releases & Code Source**<br><sub>Sommes de contrôle SHA-256 certifiées, archives et historique</sub> |

### Programmes Bêta & Canary — Accès anticipé

<p align="center">
  <img alt="Canal Stable" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/Versions/Stable-cropped-1024.png" width="100"> &nbsp;&nbsp;
  <img alt="Canal Bêta" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/Versions/Beta-cropped-1024.png" width="100"> &nbsp;&nbsp;
  <img alt="Canal Canary" src="https://raw.githubusercontent.com/FantasmaGlad/Bobine/main/Assets/Images/Versions/Canary-cropped-1024.png" width="100">
  <br>
  <sub>Stable · Bêta · Canary</sub>
</p>

Envie d'essayer les prochaines fonctionnalités avant leur sortie stable ? En plus de Stable, Bobine propose deux canaux de mise à jour anticipée : **Bêta**, un lot de fonctionnalités/correctifs que je sélectionne et publie manuellement quand il est prêt, et **Canary**, une pre-release unique toujours à jour, reconstruite automatiquement depuis le tout dernier commit de `main` — zéro curation. Aucun des deux ne demande de suivre un numéro de version ; une version stable équivalente ou plus récente les remplace toujours automatiquement, et vous pouvez repasser en Stable à tout moment sans perte de données.

| Canal | Cadence de publication | Curation | Pour qui | Tag |
| :--- | :--- | :--- | :--- | :---: |
| **Stable** | Une release par version, taguée | Entièrement testée | Exploitation en salle de sport — le choix par défaut recommandé | `Vx.y.z` |
| **Bêta** | Par lots, publiés manuellement quand prêts | Je la curate moi-même | Premiers adoptants voulant les prochaines fonctionnalités sans le flux quotidien | `beta` |
| **Canary** | À chaque commit sur `main` | Aucune — brute et immédiate | Développeurs et utilisateurs avancés voulant la toute dernière version, quitte aux aspérités | `canary` |

[**Voir la release Bêta**](https://github.com/FantasmaGlad/Bobine/releases/tag/beta) · [**Voir la release Canary**](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) — mêmes plateformes que ci-dessus (`.exe`, `.deb`, `.dmg`, `bobine-assistant`, `install.sh`), noms de fichiers suffixés `-beta`/`-canary` plutôt qu'un numéro de version.

Comment rejoindre un canal durablement, pour que les futures mises à jour continuent de proposer des builds Bêta ou Canary :
- **Déjà installé** → Réglages → Mises à jour logicielles → « Canal de mise à jour », basculer sur Bêta ou Canary.
- **Installateur appliance headless** → `sudo ./install.sh --channel=beta` ou `--channel=canary`
- **Bobine Assistant (assistant d'installation à distance)** → choisir le canal à l'étape Options.

Détails complets sur le fonctionnement de ces canaux (détection de mise à jour, downgrade, processus de publication) : [Architecture Technique § Canal de mise à jour](docs/ARCHITECTURE.md#7-script-dinstallation--services-systemd).

Pages dédiées : [Bobine Stable](https://bobine.fit/fr/canaux/stable) · [Bobine Bêta](https://bobine.fit/fr/canaux/beta) · [Bobine Canary](https://bobine.fit/fr/canaux/canary) · [tous les canaux](https://bobine.fit/fr/canaux) · [nouveautés](https://bobine.fit/fr/nouveautes). Versions courantes lisibles par machine : [`latest.json`](https://bobine.fit/latest.json) et le [flux Atom](https://bobine.fit/feed.xml).

---

**L'alternative open source et auto-hébergée à Les Mills Cinema, Wexer et Screenly Anthias — régie vidéo professionnelle, affichage dynamique et diffusion de cours collectifs 100% hors-ligne pour salles de sport et studios de fitness.**

Bobine transforme n'importe quelle tablette, PC de bureau, Mac ou mini PC dédié bon marché en une véritable régie audiovisuelle autonome :
- **Diffusion Cinéma 4K 60 fps & Moteur Gapless A/B Deck** : Planifie et diffuse des cours de fitness sur grand écran avec un catalogue immersif façon plateforme de streaming, un écran de pause moderne type Netflix, un double décodeur vidéo fluide éliminant tout écran noir, et une accélération matérielle complète multi-OS (VA-API, VideoToolbox, MediaCodec, QuickSync).
- **Double canal indépendant & Mode Pupitre Studio** : Pilote simultanément et sans interférence un écran câblé (TV/projecteur HDMI) et un écran réseau (navigateurs LAN/Wi-Fi), ou associe un pupitre tactile coach (`/grid`) à l'écran de projection (`/cinema`).
- **Borne adhérents & Système de Notation 5 Étoiles** : Permet aux membres de lancer des cours à la demande depuis une borne interactive verrouillée, de noter leur séance (1 à 5 étoiles) sur le pupitre ou sur grand écran à la télécommande/manette, ou de piloter la musique depuis leur smartphone via un simple QR code.
- **Tableau de Bord Métriques & Télémétrie Matérielle** : Suivi complet de l'assiduité des séances, taux de complétion, histogramme d'affluence horaire 24h et supervision matérielle en direct (puissance en Watts, températures, charge CPU/GPU et RAM avec marque, technologie et fréquence max, et modèles des composants).
- **Mode Audio Coach & Radio 24/7** : Anime les séances rythmées sur des boucles visuelles cinématiques et assure une ambiance musicale ininterrompue.
- **100% Souverain & Local-first** : Aucune dépendance au cloud, zéro abonnement, zéro télémétrie, aucune connexion internet requise après installation — conçu pour une stabilité industrielle 24/7 sans interruption.

---

## Pourquoi Bobine

Les salles de cours collectifs diffusent de plus en plus des cours vidéo pré-enregistrés, animés par un coach à l'écran (« cours virtuels »). Les solutions propriétaires comme Les Mills Cinema ou les plateformes cloud comme Wexer enferment dans une plateforme fermée, un abonnement récurrent par écran et une dépendance critique à Internet. Bobine offre la même expérience en salle — cours planifiés, borne à la demande, expérience adhérent soignée — en gardant le contrôle total :

- **Vous êtes propriétaire.** Vos vidéos, votre matériel, votre planning. Pas d'abonnement, pas de dépendance à un éditeur, pas de compte.
- **Ça marche hors ligne.** Une fois installé, la salle n'a besoin d'aucune connexion internet pour diffuser les cours.
- **Le code est ouvert.** Licence AGPL-3.0, auditable — l'avenir du système ne dépend pas des décisions commerciales d'un éditeur tiers.
- **Ça tourne sur du matériel standard ou bon marché.** Votre ordinateur personnel ou un mini PC d'occasion (type Dell Wyse 5070) suffit — aucune licence récurrente par écran.
- **C'est autonome.** Démarrage automatique à la mise sous tension, reprise après coupure de courant, redémarrage automatique d'un composant en panne.
- **Distribution Tor (.onion) & Souveraineté.** Dépôt APT et site également servis sur le réseau Tor pour préserver la vie privée et contourner les pare-feu restrictifs.

### Positionnement & Alternatives
- **Alternative aux plateformes fitness propriétaires (Les Mills Cinema, Wexer Virtual, Fitness On Demand, Radical Fitness / catalogues de franchise type Yako)** : Bobine supprime les redevances mensuelles par écran et le verrouillage commercial. Vous restez maître de vos vidéos (cours maison ou libres), de la promotion de vos coachs résidents et de votre grille horaire, avec un fonctionnement 100% hors-ligne sans risque de panne internet.
- **Alternative aux solutions d'affichage dynamique générique (Screenly Anthias, Yodeck, Xibo, TouchPlayer, Waves System)** : Contrairement aux afficheurs passifs limités à des boucles d'images publicitaires, Bobine est conçu pour le métier du fitness : reprise sur coupure de courant & anti-veille, borne tactile adhérents avec décompte, télécommande coach par QR code local sans application, et radio d'ambiance 24/7 avec annonces vocales programmées sur mini PC Debian 13 avec décodage matériel VA-API (< 8% CPU).
- **Communauté & Annuaire** : Retrouvez également la fiche du projet et ses alternatives libres sur [AlternativeTo](https://alternativeto.net/software/fantasmaglad-bobine/about/).

Utilisateurs types : studios, salles de sport, espaces fitness d'hôtels et d'entreprises, kinés et centres de rééducation, studios de danse et de cycling — quiconque diffuse des vidéos de cours planifiées ou à la demande sur un écran, et cherche une alternative souveraine sans abonnement.

Bobine est agnostique aux programmes : les catégories de cours sont libres, il s'adapte donc à n'importe quel catalogue de cours collectifs, cycling, renforcement, mobilité ou bien-être.


---

## Fonctionnalités

- **Planification vidéo** — construisez un planning hebdomadaire ; les cours démarrent automatiquement au bon moment sur le bon écran.
- **Borne cinéma à la demande** — un écran plein écran côté adhérent pour choisir et lancer un cours soi-même avec démarrage instantané et reprise sur coupure.
- **Deux sorties d'écran indépendantes** — pilotez un écran câblé (HDMI) et un écran réseau séparément, chacun avec son contenu.
- **Télécommande mobile** — contrôlez la lecture (play, pause, avance, suivant) depuis n'importe quel téléphone du réseau local : widget « En cours », lancement d'un cours avec aperçu (miniature, durée), choix des sous-titres et saut de chapitre.
- **Sous-titres & chapitres** — pistes `.srt`/`.vtt` en plusieurs langues par cours, chapitres importés (JSON, WebVTT ou texte « 05:00 Titre ») ou extraits du fichier vidéo, repères sur la progression et bandeau à l'écran.
- **Support universel des contrôles (Manettes, Télécommandes, Souris, Tactile)** — la borne cinéma adhérent, le pupitre studio, le kiosque et l'écran radio répondent immédiatement à tous les périphériques : manettes de jeu (Xbox, PlayStation, 8BitDo, Switch Pro via l'API Gamepad HTML5 standard), télécommandes physiques USB/Bluetooth à dongle (flèches, OK, retour, play/pause, pistes, volume), souris et écrans tactiles.
- **Mode coach audio** — diffusez des cours audio sur les enceintes de la salle avec un fond visuel animé ou fixe à l'écran.
- **Radio intégrée** — un lecteur de musique d'ambiance 24/7 façon Spotify, avec fondu enchaîné, aléatoire, répétition et rappels vocaux programmés (« replacez vos poids », etc.).
- **Deux sorties radio indépendantes** — la radio câblée et la radio réseau ont chacune leur playlist, leur volume, leurs rappels et leur planning : de quoi gérer plusieurs radios dans la salle. Un interrupteur **Radio** sur la sortie câblée transforme l'écran physique en poste radio, à la demande.
- **Onglet Périphériques** — sorties audio, appairage Bluetooth et Wi-Fi de la machine qui diffuse, depuis l'interface. Désactivé par défaut ; l'écran local est de confiance, tout autre appareil saisit un PIN à 6 chiffres défini depuis l'écran local. Les changements de Wi-Fi demandent une confirmation et reviennent à l'ancien réseau après 60 s sans elle ; le mot de passe d'un nouveau réseau se saisit uniquement sur l'écran local. Android propose l'audio, le Bluetooth et le Wi-Fi en lecture seule avec des raccourcis vers les réglages du système ; Windows et macOS sont expérimentaux tant qu'ils ne sont pas validés sur du matériel réel.
- **Bibliothèque radio** — une barre horizontale de cinq sections (morceaux, playlists, artistes & albums, tags & styles, import) avec tri, vue grille ou liste dense et filtre par playlist.
- **Tous les formats de téléviseur** — `/radio`, `/kiosk` et `/cinema` s'adaptent aux ratios atypiques ; ajoutez `?safe=3` à l'adresse de l'écran pour les téléviseurs qui rognent l'image (overscan).
- **Égaliseur et basses** — égaliseur 5 bandes, renfort des basses, loudness, protection anti-saturation et trois préréglages (Bass Boost, Voix Boost, Adoucis), réglés par sortie, sans alourdir : le traitement est fait par le lecteur.
- **Gestion de bibliothèque simple** — import par glisser-déposer, envoi en lot, catégories libres, sélection groupée, progression fichier par fichier, miniatures automatiques.
- **Local-first et résilient** — reprise automatique après un redémarrage ou une coupure, et un chien de garde qui redémarre un composant mort.
- **Admin web, zéro installation client** — tout s'administre depuis un navigateur ; les écrans adhérents et les télécommandes ne sont que des pages web.
- **Anti-veille Screen Wake Lock API** — empêche la mise en veille intempestive de l'écran pendant les cours et la radio sur tous les navigateurs modernes.
- **Réencodage avec accélération matérielle multi-OS** — encodage GPU natif via MediaCodec (Android), VideoToolbox (Apple Silicon M1-M4), VA-API (Linux) et QuickSync (Windows), avec repli CPU optimisé `libx264 ultrafast`.
- **Qualité vidéo intégrale (2K et 4K natifs)** — préservation intégrale des résolutions ultra haute définition sans sous-échantillonnage destructif, format MP4 optimisé streaming immédiat (`+faststart`).
- **Annulation réactive & estimation en direct (ETA)** — arrêt immédiat de FFmpeg au clic sur la croix (X), purge automatique des fichiers temporaires et affichage en temps réel du temps restant et de la vitesse.
- **Miniatures Full HD 1080p & navigation fluide (fast seek)** — vignettes de haute précision pour écrans 4K et intervalles de trames clés resserrés pour un déplacement temporel instantané sans latence.

---

## Matériel supporté

Bobine est un logiciel léger et optimisé, conçu pour fonctionner avec fluidité sur une très large gamme d'équipements existants, neufs ou reconditionnés (architectures **x86-64** et **ARM64** natives) :

- **Ordinateurs portables (Laptops Windows 11/10 x86-64 & ARM64 Snapdragon, macOS, Linux et Google Books)** :
  - **Tous PC portables x86-64** : HP Pavilion, Acer Aspire, Lenovo IdeaPad/ThinkPad, Dell Inspiron/Latitude, ASUS Vivobook, etc.
  - **PC portables ARM Qualcomm Snapdragon** : appareils sous **Windows 11 ARM64** (`Bobine-Setup-5.0.0-arm64.exe`) ou **Linux ARM64** (`bobine_5.0.0_arm64.deb`) équipés des puces **Qualcomm Snapdragon X Elite / X Plus** (Surface Laptop 7, Lenovo Yoga Slim 7x, ThinkPad T14s Gen 6, ASUS Vivobook S 15, Dell XPS 13 / Inspiron ARM, HP OmniBook X...).
  - **Google Books (ordinateurs portables Google Book / Aluminium OS)** : prise en charge native via l'application Android ARM64 (`Bobine-5.0.0.apk`, et bientôt disponible nativement sur le Google Play Store) ainsi que via le sous-système Linux Debian ARM64/x86-64 intégré.
  - **Gamme Apple MacBook** : MacBook Air & MacBook Pro (puces Apple Silicon M1, M2, M3, M4 et modèles Intel).
  - **Deux modes d'utilisation au choix** :
    - *Mode Pupitre Studio (Double écran)* : l'écran du PC portable sert de console régie tactile ou souris/touchpad (`/grid` pour choisir et piloter les cours), tandis que la sortie HDMI diffuse le flux vidéo épuré plein écran (`/cinema`) sur la TV ou le vidéoprojecteur sans afficher de bureau ni de curseur aux adhérents.
    - *Mode Headless (Capot fermé / Clamshell)* : le PC portable est posé dans un meuble ou un rack régie et diffuse sur la TV grand écran capot fermé (sans se mettre en veille), piloté à distance depuis un smartphone (`/mobile` ou `/coach`).
- **Tablettes Android & Bornes Tactiles ARM (Régie autonome tout-en-un)** :
  - **Xiaomi Pad 8** (tablette de référence officielle, validée sur banc de test et en conditions réelles de salle), **Xiaomi Pad 6 & 7**, Samsung Galaxy Tab série S, Lenovo Tab série P (tablettes ARM64 disposant d'une sortie USB-C DisplayPort vers HDMI).
  - *Deux modes disponibles* : Mode Pupitre tactile interactif (`/grid` sur la tablette + `/cinema` sur TV HDMI), ou Mode Headless avec écran d'accueil sobre et bouton de bascule rapide.
- **Android TV, Google TV & Box TV Multimédia (Diffusion directe sur téléviseur)** :
  - **Chromecast avec Google TV** (HD / 4K), **Nvidia Shield TV / Pro**, **Xiaomi TV Box S (2nd Gen)**, **Nokia Streaming Box 8000/8010**, **Strong Leap-S3**, téléviseurs connectés sous Android TV & Google TV (Sony, Philips, TCL, Hisense...).
  - *Deux modes d'utilisation au choix* :
    - *Client Kiosque Réseau (Recommandé & zéro configuration)* : la box TV se connecte au serveur Bobine principal du studio (PC, Mac, Mini PC ou Tablette sur le même réseau Wi-Fi/Ethernet) et diffuse le catalogue interactif plein écran (`/kiosk`) navigable à 100% à la télécommande d'origine.
    - *Serveur Autonome Dédié* : la box TV exécute le moteur Bobine complet en local (FastAPI + SQLite). **Exigence de stockage externe** : en raison des 4 à 8 Go de mémoire flash eMMC interne des box TV, brancher une **clé USB 3.0 ou un SSD externe** (FAT32/exFAT) en USB-OTG pour héberger la bibliothèque vidéo de cours sans saturer la mémoire interne.
- **PC fixes, Stations ARM64 & Postes de travail de bureau** :
  - Toute tour ou PC de bureau Windows/Linux x86-64 ou ARM64 (≥ 4 Go de mémoire vive).
  - **Stations de travail & Mini PC Linux ARM64** : **NVIDIA DGX Spark (Grace Blackwell GB10)**, NVIDIA Jetson Orin, Raspberry Pi 5 (8 Go / 16 Go), Orange Pi 5 Max, Radxa Rock 5B, etc. (via le paquet `.deb` `arm64`, le dépôt `apt.bobine.fit`, `install.sh` ou `bobine-assistant-arm64`).
  - Apple **Mac Mini** & **iMac** (stations régie particulièrement compactes et silencieuses pour les studios de fitness).
- **Mini PC & Boîtiers compacts dédiés (Idéaux pour une diffusion 24/7 en salle)** :
  - Mini PC x86-64 économiques ou reconditionnés : **Dell Wyse 5070**, **HP ProDesk 400/600 DM**, **Lenovo ThinkCentre Tiny**, **Beelink Mini S12/EQ12**, Intel NUC.
  - Mini PC & SBC ARM64 : **NVIDIA DGX Spark**, **Raspberry Pi 5**, **Orange Pi 5 Max**, **Radxa Rock 5B**.
  - Fonctionnement autonome 100% sans écran ni clavier (appliance Linux Debian 13 x86-64 & ARM64) avec démarrage automatique et relance continue sans veille.
- **Écrans, Vidéoprojecteurs & Affichage** :
  - Tout téléviseur de salle, écran géant, moniteur ou vidéoprojecteur raccordé en **HDMI**, **DisplayPort** ou **USB-C DisplayPort**.
  - Bornes tactiles avec dalle USB/HDMI pour le libre-service adhérents.
  - Écrans d'appoint : toute smart TV, tablette ou smartphone connecté au Wi-Fi local via son navigateur.
- **Systèmes sonores & Sono de salle** :
  - Sortie Jack 3,5 mm, HDMI audio, carte son USB externe, enceinte Bluetooth, ou raccordement direct sur ampli de salle de sport / table de mixage.
- **Télécommandes & Pilotage à distance** :
  - **Télécommande mobile sans fil** : accessible immédiatement par QR code depuis n'importe quel smartphone iOS ou Android sans aucune application à installer.
  - **Télécommandes physiques USB** : prise en charge native des télécommandes multimédias sans fil (Air Mouse, présentateurs à dongle USB 2,4 GHz) reconnues comme clavier standard sans pilote.

> Pour les détails techniques avancés (accélération matérielle multi-OS, empreinte mémoire, schémas de bus et architecture Linux embarquée), consultez la [**Documentation technique (docs/ARCHITECTURE.md)**](docs/ARCHITECTURE.md).

### Navigateurs supportés

<p align="left">
  <a href="https://www.mozilla.org/fr/firefox/"><img src="Assets/Images/firefox.svg" alt="Firefox" width="56" align="left" hspace="12" /></a>
  <b>Bobine soutient fièrement Firefox.</b> L'interface d'administration et tous les lecteurs ouverts depuis un autre appareil (<code>/radio</code>, <code>/kiosk</code>, <code>/cinema</code>, <code>/coach</code>, <code>/mobile</code>) visent Firefox (version courante et ESR, bureau et Android) au même titre que Chrome, Edge et Safari — une seule base de code, détection de fonctionnalités uniquement, jamais de détection de navigateur.
</p>

| Navigateur | Statut |
|---|---|
| **Firefox** (Windows, macOS, Linux, Android — version courante, précédente et ESR) | **Supporté** — vérifié de bout en bout sur Firefox 157 / Linux (17 contrôles automatiques en CI, dont la reprise d'un envoi après une coupure réseau). Windows, macOS, Android et ESR pas encore mesurés  (le ralentissement d'import signalé un jour venait d'une fuite mémoire d'un autre logiciel de ce poste, pas de Bobine) |
| Chrome / Chromium / Edge | Supporté (moteur de référence du kiosque sur l'appliance headless) |
| Safari / navigateurs iOS (WebKit) | Supporté au mieux |
| Dérivés de Firefox (LibreWolf, Waterfox, Floorp, Zen) | Au mieux (même moteur Gecko) |

Le décodage vidéo matériel dépend du navigateur et du système (HEVC/AV1 en particulier) : quand un navigateur ne sait pas décoder une vidéo, Bobine lui sert une version H.264 compatible (produite à la demande, l'original reste intact) — voir *Réglages → Compatibilité navigateur* pour un diagnostic local. Voir [`scripts/browser-bench/`](scripts/browser-bench/README.md) pour reproduire les mesures sous Firefox. *Firefox est une marque de la Mozilla Foundation ; son logo n'est utilisé ici que pour indiquer la compatibilité, sans affiliation ni parrainage.*

---

## Modes d'installation & de déploiement

Bobine propose différentes méthodes d'installation selon vos besoins et votre profil d'usage :

1. **Option 1 : Applications natives (La plus simple pour tablettes, ordinateurs portables et postes de bureau)** — Android & Google Books (`.apk`), Windows 11/10 x86-64 & ARM64 Snapdragon (`.exe`), Linux Desktop x86-64 & ARM64 (`.deb` & dépôt APT) et macOS (`.dmg`). Installation en 1 clic, fonctionnement autonome hors ligne et intégration système native.
2. **Option 2 : Appliance Linux dédiée headless (Pour les salles autonomes & la gestion fine)** — Transforme un mini PC dédié x86-64 (type Dell Wyse 5070) ou ARM64 (NVIDIA DGX Spark, Raspberry Pi 5, Orange Pi 5 Max) en borne vidéo 24/7 locked-in démarrant directement en kiosque X11 plein écran sans aucun bureau graphique parasite, avec gestion automatique de la reprise sur incident et anti-veille. Installation rapide en 1 ligne CLI.
3. **Option 3 : Assistant graphique d'installation Tauri (`assistant/`)** — Un outil de bureau moderne (x86-64 & ARM64) pour découvrir, auditer et déployer à distance vos mini PC via le réseau local en SSH.

---

### Option 1 — Applications natives (Android, Google Books, Windows, Linux & macOS)

#### Sur Android (Tablettes & Bornes Tactiles) et Google Books (Aluminium OS)

Voir aussi [Bobine sur Google Book](https://bobine.fit/fr/google-book).

1. **Téléchargez** [**`Bobine-5.0.0.apk`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.apk) directement sur votre tablette ou votre ordinateur portable **Google Book (Aluminium OS)** (bientôt disponible nativement sur le Google Play Store ; sur Google Book, vous pouvez également installer le paquet `.deb` via le sous-système Linux Debian ARM64/x86-64).
2. **Installez le fichier APK** (autorisez l'installation d'applications de sources inconnues si votre système vous le demande).
3. **Lancez Bobine** :
   - Le service d'arrière-plan persistant (`ForegroundService`) démarre automatiquement le serveur FastAPI embarqué (Chaquopy / CPython 3.13) et acquiert le verrou mDNS.
   - L'écran tactile de la tablette affiche immédiatement l'interface en grille optimisée tactile (`/grid`) pour planifier, lancer et piloter les cours.
   - Raccordez un adaptateur ou dock USB-C vers HDMI relié à votre téléviseur ou vidéoprojecteur : Bobine bascule automatiquement la diffusion plein écran propre (`/cinema`) sur l'écran externe, sans barre d'état système.
   - Les autres appareils connectés au Wi-Fi accèdent à la télécommande ou à l'administration via `http://bobine.local:8000`.

#### Sur Android TV & Google TV (Box TV, Clés HDMI & Smart TV)

Voir aussi la page web [Bobine sur Android TV & Google TV](https://bobine.fit/fr/android-tv) (tableau de téléchargement et FAQ).

1. **Téléchargez** [**`Bobine-TV-5.0.0.apk`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-TV-5.0.0.apk) (ou depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Installez l'APK sur votre téléviseur ou boîtier TV** :
   - Transférez le fichier via une clé USB branchée sur la box (avec un gestionnaire de fichiers comme *AnExplorer* ou *File Commander*), ou sans fil via une application de transfert comme *Send Files to TV* ou *Downloader*.
   - Autorisez l'installation d'applications inconnues dans les *Paramètres → Sécurité et restrictions* de votre TV.
3. **Lancez Bobine depuis l'écran d'accueil TV** :
   - L'application apparaît directement dans la ligne des applications de l'écran d'accueil Android TV / Google TV grâce à son lanceur Leanback et sa bannière 16:9 officielle.
   - **Mode d'affichage automatique** : l'application charge directement l'interface grand écran optimisée pour télécommande (`/kiosk`), avec contrôle intégral au D-Pad (flèches directionnelles, touche centrale OK, touche Retour pour revenir en arrière).
   - **Stockage externe amovible (Mode Serveur Autonome)** : si vous utilisez la box TV comme serveur principal indépendant, branchez une clé USB ou un disque SSD externe formaté en FAT32 ou exFAT. Bobine détecte automatiquement le support amovible et y loge vos cours vidéo sans encombrer la mémoire interne de la box.

#### Sur Windows (11, 10, Windows IoT & PC ARM Qualcomm Snapdragon)

1. **Téléchargez** l'installeur correspondant à votre processeur :
   - **PC x86-64 (Intel / AMD)** : [**`Bobine-Setup-5.0.0.exe`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-Setup-5.0.0.exe)
   - **PC ARM64 (Qualcomm Snapdragon X Elite / X Plus)** : [**`Bobine-Setup-5.0.0-arm64.exe`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-Setup-5.0.0-arm64.exe)
2. **Lancez l'installeur** et suivez l'assistant (choix français/anglais, acceptation de la licence AGPL-3.0).
   - Installe Bobine dans `Program Files\Bobine`.
   - Place un raccourci avec l'icône officielle Bobine sur votre **Bureau** et dans le Menu Démarrer.
   - Enregistre le lancement silencieux en tâche de fond à l'ouverture de session Windows.
   - Configure automatiquement une règle de pare-feu Windows Defender pour autoriser les télécommandes mobiles sur le réseau local.
   - *Note* : Si Windows SmartScreen affiche un avertissement « éditeur non reconnu », cliquez sur **Informations complémentaires → Exécuter quand même** (Bobine est un logiciel libre et gratuit sans certificat commercial payant).
3. **Double-cliquez sur l'icône Bureau Bobine** :
   - Le moteur backend démarre instantanément en tâche de fond **sans aucune fenêtre console noire**.
   - Votre navigateur par défaut s'ouvre automatiquement sur l'interface d'administration : `http://127.0.0.1:8000`.
   - Une icône compagnon apparaît dans la zone de notification (systray, près de l'horloge) pour rouvrir l'admin, lancer le kiosque plein écran, redémarrer le serveur ou quitter.
   - Si Bobine tourne déjà en arrière-plan, cliquer sur l'icône Bureau rouvre immédiatement votre navigateur sans générer d'erreur de port ni de doublon.
4. **Accès depuis les autres appareils** : ouvrez `http://bobine.local` depuis n'importe quel smartphone, tablette ou ordinateur connecté au même réseau Wi-Fi local. Les données applicatives (vidéos, base SQLite, logs) sont stockées dans `%ProgramData%\Bobine`.

#### Sur Linux avec bureau (Debian, Ubuntu et dérivés graphiques — x86-64 & ARM64)

**Méthode recommandée — Dépôt APT officiel ([apt.bobine.fit](https://apt.bobine.fit), architectures `amd64` & `arm64`) :**
Configurez le dépôt APT officiel signé cryptographiquement par GPG pour installer Bobine (sur PC x86-64, portable ARM Snapdragon sous Linux, station **NVIDIA DGX Spark**, Raspberry Pi 5, etc.) et recevoir automatiquement les futures mises à jour lors de vos `sudo apt upgrade` habituels :
```bash
# 1. Clé publique GPG officielle
curl -fsSL https://apt.bobine.fit/bobine.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/bobine.gpg

# 2. Ajout du dépôt APT officiel (canal stable ; remplacer 'stable' par 'beta' ou 'canary' pour les pré-versions)
echo "deb [signed-by=/etc/apt/keyrings/bobine.gpg] https://apt.bobine.fit/ stable main" | sudo tee /etc/apt/sources.list.d/bobine.list

# 3. Installation et mises à jour
sudo apt update && sudo apt install bobine
```

**Option sécurisée — Dépôt APT via Tor (.onion) :**

Détails et vérifications : [Bobine sur Tor](https://bobine.fit/fr/tor).
Pour installer et mettre à jour Bobine de manière totalement confidentielle sans révéler l'adresse IP de votre salle :
```bash
sudo apt install apt-transport-tor
curl -fsS --socks5-hostname 127.0.0.1:9050 http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/bobine.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/bobine.gpg
echo "deb [signed-by=/etc/apt/keyrings/bobine.gpg] tor+http://rzvwjat5pidtxtwzcsvew7yc5ugfjvzz432ecpn3s5mlch4cs7vvmqad.onion/ stable main" | sudo tee /etc/apt/sources.list.d/bobine-onion.list
sudo apt update && sudo apt install bobine
```
Ou via le script automatisé (vérification d'empreinte GPG par Tor) :
```bash
curl -fsSL https://bobine.fit/install-tor.sh | bash
```

**Méthode alternative — Paquet autonome `.deb` (Installation hors ligne ou via logithèque) :**
1. **Téléchargez** [**`bobine_5.0.0_amd64.deb`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine_5.0.0_amd64.deb) (PC x86-64) ou [**`bobine_5.0.0_arm64.deb`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/bobine_5.0.0_arm64.deb) (ARM64 : NVIDIA DGX Spark, Snapdragon, Raspberry Pi 5, etc.).
2. **Installez le paquet** en double-cliquant dessus (Centre d'Applications Ubuntu / GNOME Software) ou en ligne de commande :
   ```bash
   sudo apt install ./bobine_*.deb
   ```
   *(Toutes les dépendances comme `ffmpeg` sont automatiquement résolues par apt, et les icônes multi-résolution sont intégrées au thème système).*

**Lancement et intégration au bureau :**
- Lancez Bobine depuis le raccourci créé sur votre **Bureau**, le menu d'applications ou tapez `bobine` dans un terminal.
- L'icône Bobine apparaît dans votre zone de notification / barre d'état (tray) et assure la supervision du moteur.
- Lancement automatique au login XDG configuré nativement.
- Vos médias et données vivent dans votre dossier utilisateur selon la norme standard XDG : `~/.local/share/bobine/`.

#### Sur macOS (Apple Silicon - M1/M2/M3/M4)

1. **Téléchargez** [**`Bobine-5.0.0.dmg`**](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.dmg) (ou depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Ouvrez le .dmg** et glissez `Bobine.app` dans votre dossier **Applications**.
3. **Lancez Bobine** depuis Applications, votre **Bureau** (raccourci créé automatiquement) ou Spotlight.
   - *Premier lancement* : Bobine n'étant pas signé par un certificat Apple Developer payant (pas de notarisation), Gatekeeper bloque le premier lancement. Selon la version de macOS, deux messages différents peuvent apparaître :
     - **« Bobine a été bloqué » / « développeur non identifié »** → Ouvrez **Réglages Système → Confidentialité et sécurité**, repérez le message, cliquez sur **Ouvrir quand même**, puis confirmez.
     - **« Bobine.app » est endommagé et ne peut pas être ouvert. Vous devez le placer dans la corbeille** → ce n'**est pas** un téléchargement corrompu — c'est la formulation (trompeuse) de Gatekeeper pour la même situation d'app non signée, sans bouton « Ouvrir quand même » disponible cette fois. Correctif via le Terminal : `xattr -cr /Applications/Bobine.app`, puis relancez l'application.
   - Dès ce premier lancement, Bobine installe son propre LaunchAgent et démarrera automatiquement à chaque connexion. Une icône dans la barre de menus permet d'ouvrir l'admin, de lancer le mode kiosque plein écran, de redémarrer le backend ou de quitter.
4. **Ouvrez l'interface** : `http://bobine.local` depuis n'importe quel appareil du réseau local (ou `http://127.0.0.1:8000` en local). Les données vivent dans `~/Library/Application Support/Bobine`.

---

### Serveurs Dédiés & Appliances Headless — Méthodes d'Installation Avancées

Pour les studios, salles de fitness et intégrateurs déployant des bornes autonomes 24/7 sur mini PC reconditionné x86-64 (Dell Wyse 5070, HP ProDesk DM...) ou station Linux ARM64 (**NVIDIA DGX Spark**, NVIDIA Jetson Orin, Raspberry Pi 5, Orange Pi 5 Max, Radxa Rock 5B) sans bureau graphique parasite :

| Méthode | Type | Matériel cible | Déploiement | Points forts & Spécifications |
| :--- | :---: | :---: | :--- | :--- |
| <img src="Assets/Images/bash.svg" width="20" height="20" valign="middle" alt="Bash"> **Installateur Bash (CLI)** | <sub>Script Shell</sub> | <sub>Debian 13 (x86-64 & ARM64)</sub> | <sub>`curl -sSL https://bobine.fit/install.sh \| bash`</sub> | <sub>• Séquence automatisée en 18 étapes</sub><br><sub>• Décodage matériel 4K (&lt; 8% CPU)</sub><br><sub>• Reprise sur incident & anti-veille</sub><br><sub>• Kiosque X11 plein écran sans veille</sub><br><sub>• Services systemd auto-réparateurs</sub> |
| <img src="Assets/Images/network.svg" width="20" height="20" valign="middle" alt="Réseau"> **Bobine Assistant (Tauri)** | <sub>Application Graphique<br>*(Tauri 2)*</sub> | <sub>Windows, macOS & Linux<br>*(x86-64 & ARM64)*</sub> | <sub>Assistant GUI par déploiement SSH</sub> | <sub>• Scan réseau complet — tous les appareils (nom, IP, OS, ports)</sub><br><sub>• SSH par mot de passe, clé importée ou clés locales auto-détectées</sub><br><sub>• Audit matériel en direct (CPU, GPU, RAM, disque)</sub><br><sub>• Orchestration visuelle en 5 étapes guidées</sub> |

#### Option 2 — Appliance Linux dédiée headless (Mini PC x86-64 & ARM64 / Debian 13)

> **Pour les salles de sport et studios recherchant une indépendance totale, zéro manipulation au quotidien et une gestion matérielle ultra-fine.**  
> Ce mode transforme un mini PC reconditionné x86-64 (Dell Wyse 5070, HP ProDesk DM, Lenovo Tiny...) ou une station/SBC ARM64 (**NVIDIA DGX Spark**, Raspberry Pi 5, Orange Pi 5 Max, Radxa Rock 5B) en serveur de diffusion vidéo 100% autonome qui démarre directement en affichage kiosque plein écran sans aucun environnement de bureau lourd.

#### 1. Préparation minimale Debian 13
1. **Téléchargez** l'image Debian 13 « Trixie » *netinst* (`amd64` ou `arm64`, ~700 Mo) sur le site officiel : <https://www.debian.org/download>.
2. **Écrivez-la sur une clé USB** (8 Go et plus) avec [balenaEtcher](https://etcher.balena.io/) ou `dd`.
3. **Démarrez le mini PC sur la clé USB** et déroulez l'installateur : décochez tous les environnements de bureau, ne gardez que **serveur SSH** et **utilitaires usuels**.

#### 2. Installation rapide en 1 ligne de commande (CLI)
Sur le mini PC (en direct ou par SSH), avec votre compte utilisateur normal (pas root) :

```bash
# Installation automatisée en 1 ligne (canal Stable) :
curl -fsSL https://bobine.fit/install.sh | bash

# Idem sur le canal Bêta (accès anticipé curé) :
curl -fsSL https://bobine.fit/install.sh | bash -s -- --channel=beta

# Ou le canal Canary (tout dernier commit de main, non testé) :
curl -fsSL https://bobine.fit/install.sh | bash -s -- --channel=canary
```

Le script récupère le code dans `~/Bobine` (en installant d'abord `git`/`curl` sur un système minimal), demande `sudo` tout seul, affiche une progression animée avec le temps de chaque étape, attend un éventuel `unattended-upgrades` en cours, corrige une horloge déréglée, puis termine par l'URL d'administration **et un code QR** pour l'ouvrir depuis un téléphone. Le relancer est sans risque : il met à jour une installation existante sur place. Ajoutez `--dry-run` pour prévisualiser chaque action.

*(Ou manuellement pour un contrôle complet des sources : `git clone https://github.com/FantasmaGlad/Bobine.git && cd Bobine && sudo ./install.sh`).*

**Ce que configure automatiquement `install.sh` :**
- Paquets système : virtualenv Python, Uvicorn, base SQLite, Chromium, FFmpeg avec décodage matériel VA-API.
- Démarrage automatique en session X11 kiosque plein écran avec suppression de toute veille d'écran.
- Automatisation de diffusion : reprise automatique sur coupure de courant et anti-veille permanente.
- Services systemd supervisés (`bobine-backend.service`, `bobine-kiosk.service`, `bobine-audio-guard.service`).
- Chien de garde (watchdog) de santé : relance automatique en cas d'anomalie et reprise sur coupure de courant.

---

### Option 3 — Assistant graphique d'installation Tauri (`assistant/`)

> **Déployez vos bornes mini PC à distance depuis votre propre poste de travail, sans toucher au terminal.**

Disponible dans le dossier [`assistant/`](assistant/) (compilé nativement pour **Windows**, **Linux x86-64** (`bobine-assistant`), **Linux ARM64** (`bobine-assistant-arm64`) et **macOS**), l'application graphique **Bobine Assistant** guide le déploiement d'une borne de bout en bout :

1. **Découverte automatique sur le réseau** : sonde le sous-réseau `/24` de chaque interface réseau locale (Wi-Fi, Ethernet, VPN) pour localiser vos bornes Bobine joignables.
2. **Déploiement SSH guidé** : connexion sécurisée (clé privée ou mot de passe), audit matériel automatique (CPU, GPU VA-API, RAM, stockage), puis exécution de `install.sh` dans un terminal émulé interactif avec barre de progression en temps réel.

---

### Ouvrir l'interface & commencer

Depuis n'importe quel appareil connecté au même réseau Wi-Fi / Ethernet :

```
http://bobine.local
```

Bobine s'annonce en **mDNS (Zeroconf/Bonjour)** sous le nom `bobine.local`. Si votre réseau local ne relaie pas le mDNS, utilisez directement l'adresse IP locale de la machine (`http://<adresse-ip>:8000` ou port 80 sur l'appliance).

---

## Utiliser Bobine

- **Interface d'admin** (`http://bobine.local`) — importez et organisez vidéos, fonds animés, cours audio et pistes radio ; créez playlists et plannings ; gérez réglages, thèmes et langue.
- **Cinéma adhérent** — l'écran câblé affiche un menu de sélection ; l'adhérent lance son cours. Les nouveaux imports y apparaissent automatiquement.
- **Écran réseau** — une seconde sortie indépendante ; choisissez ce qu'affiche chaque écran dans *Paramètres → Sortie vidéo*.
- **Télécommande mobile** — ouvrez `http://bobine.local` sur un téléphone ; l'affichage s'adapte en télécommande pour le staff.
- **Radio** — ouvrez `/radio?channel=network` sur un appareil dédié pour diffuser la musique d'ambiance en continu (`/radio` reste un alias) ; `/radio?channel=cable` est la radio de la sortie câblée, activée par le bouton *Radio* de *Sortie Câblé*. Pilotage et réglages du son depuis l'onglet *Radio* de l'admin.
- **Synchronisation des écrans** — *Paramètres → Synchronisation des écrans* vide le cache de chaque écran connecté, le recharge avec les derniers assets et redémarre les services.
- **Sauvegarde & Restauration** — depuis *Paramètres → Sauvegarde & Restauration*, téléchargez une archive ZIP complète de votre base SQLite et de vos configurations, ou restaurez un fichier de sauvegarde précédent directement depuis le navigateur.
- **Remise à zéro des données** — depuis *Paramètres → Zone de danger*, remettez à zéro les données de l'application (base SQLite et médias) tout en conservant le logiciel installé.

---

## Santé et supervision

Bobine expose un point de contrôle de santé lisible par machine :

```
GET http://bobine.local/api/health
```

Il rapporte l'état de la base **SQLite** et du **kiosque Chromium**, et renvoie `200` si tout va bien ou `503` si un composant critique est mort. Un **chien de garde** local le sonde et redémarre automatiquement un composant en panne (backend ou kiosque) : la salle se rétablit sans intervention. Tous les services redémarrent aussi automatiquement après une coupure de courant.

---

## Désinstallation

**Sous Windows**, désinstallez comme n'importe quelle application de bureau : ouvrez *Paramètres → Applications → Applications installées* (ou le panneau classique *Programmes et fonctionnalités*), cherchez Bobine, et choisissez Désinstaller. Cela retire le programme installé ainsi que les raccourcis Menu Démarrer/démarrage automatique ; `%ProgramData%\Bobine` (vos vidéos, la base de données et les logs) est conservé pour qu'une réinstallation retrouve vos données.

**Sous Linux (bureau)**, désinstallez via votre logithèque ou en ligne de commande :
```bash
sudo apt remove bobine
```
Pour purger également la configuration système, utilisez `sudo apt purge bobine`. Vos données utilisateur (`~/.local/share/bobine/`) restent conservées.

**Sous macOS**, quittez Bobine depuis l'icône de la barre de menus, faites glisser `Bobine.app` du dossier Applications vers la Corbeille, puis supprimez `~/Library/LaunchAgents/com.bobine.app.plist` pour désactiver le lancement automatique. Vos données personnelles sous `~/Library/Application Support/Bobine` restent conservées.

Sur l'**appliance headless**, utilisez la commande d'administration dédiée :
```bash
sudo ./install.sh --uninstall --purge
```
Ajoutez `--purge-data` pour retirer aussi les médias importés (irréversible). Les paquets système partagés sont conservés. Voir `sudo ./install.sh --help` pour toutes les options.

---

## Comment ça marche

Bobine est une machine hôte unique sur votre réseau local qui fait tourner :

- un backend **FastAPI** avec **SQLite** pour le stockage ;
- un kiosque **Chromium** en plein écran (X11) pour l'écran câblé (sur les appliances dédiées) ;
- une interface **Next.js** (admin, borne adhérent, télécommande mobile), servie en pages statiques depuis la même machine.

Les autres écrans (écran réseau, télécommandes, PC d'admin) sont de simples navigateurs pointant vers la machine hôte Bobine. Les médias ne quittent jamais votre réseau.

Pour l'architecture complète, le modèle de données, le contrat réseau et la référence API, voir **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Sécurité

Signalez les vulnérabilités en privé, jamais dans un ticket public : utilisez le [signalement privé de vulnérabilité GitHub](https://github.com/FantasmaGlad/Bobine/security/advisories/new) ou écrivez à [security@bobine.fit](mailto:security@bobine.fit). Les rapports contenant des détails exploitables doivent être chiffrés avec la clé OpenPGP `23CA D324 C507 FB0F 97E6 AECA 6E4C 020E F8BD FEB2` (Ed25519, expire le 2028-10-06), publiée dans [`docs/security/`](docs/security/bobine-security-public-key.asc), sur <https://bobine.fit/.well-known/security.asc>, sur <https://security.bobine.fit> et via `gpg --locate-keys security@bobine.fit` : vérifiez que l'empreinte correspond sur au moins deux canaux. Créez votre propre paire de clés et joignez votre clé publique pour que nous puissions répondre chiffré. Politique complète, périmètre et délais : [docs/fr/SECURITY.md](docs/fr/SECURITY.md).

---

## Licence

Bobine est un logiciel libre sous licence **GNU Affero General Public License v3.0 (AGPL-3.0)** — voir [`LICENSE`](LICENSE). Si vous exploitez une version modifiée pour fournir un service en réseau, vous devez mettre à disposition le code source correspondant sous la même licence.

---

## FAQ

**Qu'est-ce que Bobine ?** Une régie vidéo libre (AGPL-3.0), auto-hébergée et 100 % hors-ligne pour salles de sport et studios : cours planifiés, borne adhérent à la demande, console coach et radio d'ambiance 24/7. C'est une alternative gratuite à Les Mills Cinema, Wexer et Screenly Anthias.

**Quelle est la dernière version ?** Les versions courantes Stable, Bêta et Canary figurent dans [`latest.json`](https://bobine.fit/latest.json) et sur [bobine.fit/fr/nouveautes](https://bobine.fit/fr/nouveautes), lues directement sur GitHub Releases.

**Fonctionne-t-il sur Android TV ?** Oui, à partir d'Android 14 : un APK dédié `Bobine-TV` s'installe sur les box et clés Android TV et Google TV, en ARM 32 comme en 64 bits. Voir [Bobine sur Android TV](https://bobine.fit/fr/android-tv).

**Fonctionne-t-il sur un Google Book ?** Oui, par l'application Android native. Voir [Bobine sur Google Book](https://bobine.fit/fr/google-book).

**Qu'est-ce que Bobine Canary ?** Le canal de mise à jour rolling, reconstruit à chaque commit de `main` sans curation. Voir [Bobine Canary](https://bobine.fit/fr/canaux/canary).

**Peut-on l'installer via Tor ?** Oui sur Debian, Ubuntu et Mint : le dépôt APT et le site sont aussi des services onion. Voir [Bobine sur Tor](https://bobine.fit/fr/tor).

**Faut-il internet ou un compte ?** Non : après l'installation, tout fonctionne hors-ligne, sans compte ni télémétrie.

---

## État et feuille de route

Bobine est utilisé en production sur du matériel dédié et sur postes de travail de bureau.

Afin de maximiser la portabilité matérielle et d'alléger l'encombrement technique dans les salles et studios, la feuille de route d'ingénierie explore activement l'extension vers des tablettes tactiles autonomes équipées d'une sortie vidéo filaire directe :
* **Tablettes Android avec sortie USB-C DisplayPort** (ex. Xiaomi Pad 6, 7 ou 8, Samsung Galaxy Tab S9/S10) : Embarquement du serveur FastAPI en local via Chaquopy et diffusion vidéo vers l'écran ou le vidéoprojecteur du studio via l'API Presentation d'Android.
* **iPads Apple avec sortie Thunderbolt / USB-C** (ex. iPad Pro à puce M1/M2/M4 avec Thunderbolt / USB 4, iPad Air M2 avec DisplayPort sur USB-C) : Un unique câble ou dock USB-C alimenté relie la tablette au vidéoprojecteur, dédiant l'écran tactile aux commandes de l'instructeur tout en propulsant le flux vidéo du cours sur le grand écran.

Les tickets et contributions sont bienvenus sur le [dépôt GitHub](https://github.com/FantasmaGlad/Bobine), dans le respect de notre [guide de contribution](docs/fr/CONTRIBUTING.md) et de notre [Code de conduite](docs/fr/CODE_OF_CONDUCT.md). Vous pouvez également soutenir et évaluer le projet sur [AlternativeTo](https://alternativeto.net/software/fantasmaglad-bobine/about/).

---

<sub>**Mots-clés :** alternative open source à Les Mills Cinema, alternative à Screenly Anthias pour salle de sport, alternative libre à Wexer Virtual et Fitness On Demand, alternative aux cours vidéo de franchise (Yako, Radical Fitness, Les Mills Virtuel), affichage dynamique fitness auto-hébergé, logiciel de planification de cours collectifs, régie vidéo salle de fitness, lecteur vidéo fitness à la demande, borne de cours virtuels en libre-service, studio de cycling indoor, diffusion vidéo cours coach, thin client, mini PC Dell Wyse 5070, signalétique hors ligne, reprise sur coupure de courant et anti-veille, musique d'ambiance salle de sport, radio fitness avec annonces vocales, local-first, FastAPI, Next.js, assistant d'installation Tauri, application de bureau Windows 11, application de bureau macOS Apple Silicon, paquet Linux Debian Ubuntu .deb, régie vidéo multi-plateforme sans abonnement.</sub>
