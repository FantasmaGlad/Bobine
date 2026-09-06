# Bobine

<p align="center">
  <img alt="Bobine" src="Assets/Images/bobine_banner.svg" width="100%">
</p>

**L'alternative open source et auto-hébergée à Les Mills Cinema, Wexer et Screenly Anthias — régie vidéo, affichage dynamique et lecteur planifié hors ligne pour salles de fitness et cours collectifs.**

Bobine transforme n'importe quel PC, Mac ou mini PC dédié bon marché en système vidéo complet pour votre salle : il planifie et diffuse des vidéos de cours collectifs pré-enregistrées sur vos écrans, permet aux adhérents de parcourir et lancer un cours à la demande depuis une borne, pilote un écran câblé et un écran réseau indépendamment, propose un mode coach audio avec fonds animés, et diffuse une musique d'ambiance 24/7. Tout tourne en local, sur votre matériel. Sans cloud, sans abonnement, sans dépendance à un éditeur, sans connexion internet après l'installation.

[Site officiel](https://bobine.fit) · [Documentation web](https://bobine.fit/fr/documentation) · [English](README.md) · [Documentation technique](docs/ARCHITECTURE.md) · [Dernière version](https://github.com/FantasmaGlad/Bobine/releases/latest)

[![CI](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg)](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml)
[![Version : v3.0.0](https://img.shields.io/badge/Release-v3.0.0-brightgreen)](https://github.com/FantasmaGlad/Bobine/releases/latest)
![Licence : AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue)
![Backend : FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![Plateformes : Windows 11 | Debian | Ubuntu | macOS](https://img.shields.io/badge/Platforms-Windows%2011%20%7C%20Linux%20%7C%20macOS-blue)
![Auto-hébergé](https://img.shields.io/badge/Auto--h%C3%A9berg%C3%A9-Local--first-4c1)

---

## Téléchargement rapide & Applications de bureau natives

Installez Bobine en quelques secondes comme une application graphique native sur votre poste de travail, ordinateur portable ou PC de régie studio :

| Plateforme | Format | Architecture | Téléchargement direct / Commande | Profil & Expérience Utilisateur |
| :--- | :---: | :---: | :---: | :--- |
| ![Windows 11](https://img.shields.io/badge/Windows_11-0078D4?style=flat-square&logo=windows11&logoColor=white) | <sub>`.exe`<br>*(Installeur)*</sub> | <sub>x86-64</sub> | [**Télécharger Bobine-Setup-3.0.0.exe**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/Bobine-Setup-3.0.0.exe) | **Windows 11, 10 & Windows IoT**<br><sub>• Assistant guidé 1 clic & raccourci Bureau</sub><br><sub>• Ouverture auto du navigateur (`http://127.0.0.1:8000`)</sub><br><sub>• Systray silencieux en tâche de fond, zéro console</sub> |
| ![Debian](https://img.shields.io/badge/Debian-A81D33?style=flat-square&logo=debian&logoColor=white) ![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=flat-square&logo=ubuntu&logoColor=white) ![Linux Mint](https://img.shields.io/badge/Linux%20Mint-87CF3E?style=flat-square&logo=linuxmint&logoColor=white) | <sub>`.deb`<br>*(Paquet)*</sub> | <sub>x86-64<br>*(amd64)*</sub> | [**Télécharger bobine_3.0.0_amd64.deb**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/bobine_3.0.0_amd64.deb) | **Debian, Ubuntu & Linux Mint**<br><sub>• Logithèque Ubuntu App Center / `apt install`</sub><br><sub>• Respect des standards XDG & raccourci Bureau</sub><br><sub>• Zone de notification système (systray)</sub> |
| ![macOS](https://img.shields.io/badge/macOS-000000?style=flat-square&logo=apple&logoColor=white) | <sub>`.dmg`<br>*(Image disque)*</sub> | <sub>Apple Silicon<br>*(arm64)*</sub> | [**Télécharger Bobine-3.0.0.dmg**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/Bobine-3.0.0.dmg) | **Apple Silicon (M1, M2, M3, M4)**<br><sub>• Glisser-déposer de `Bobine.app` dans Applications</sub><br><sub>• Icône native Retina `.icns` & barre de menus</sub><br><sub>• Démarrage automatique au login (LaunchAgent)</sub> |
| ![Android](https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white) | <sub>`.apk`<br>*(Paquet)*</sub> | <sub>ARM64</sub> | <sub>*Prochainement...*</sub> | **Tablettes Android & Bornes Tactiles ARM**<br><sub>• Sortie vidéo filaire USB-C DisplayPort (Xiaomi Pad 6/7/8, Galaxy Tab)</sub><br><sub>• Pupitre coach tactile & régie autonome (Chaquopy à l'étude)</sub><br><sub>• Faisabilité en cours pour étendre la portabilité</sub> |
| ![iOS / iPadOS](https://img.shields.io/badge/iOS%20%2F%20iPadOS-000000?style=flat-square&logo=apple&logoColor=white) | <sub>App iPadOS<br>*(Piste explorée)*</sub> | <sub>ARM64 (Apple Silicon)</sub> | <sub>*Piste explorée...*</sub> | **iPads & Tablettes Tactiles Apple**<br><sub>• Sortie vidéo filaire USB-C (DisplayPort) ou Thunderbolt (iPad Pro M-series, iPad Air)</sub><br><sub>• Pupitre coach tactile & régie vidéo autonome sur grand écran</sub><br><sub>• Piste prospective pour étendre la portabilité</sub> |
| ![Bobine Assistant](https://img.shields.io/badge/Bobine_Assistant-FFC131?style=flat-square&logo=tauri&logoColor=black) | <sub>Binaire natif<br>*(Tauri 2)*</sub> | <sub>x86-64 (Linux)</sub> | [**Télécharger bobine-assistant**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/bobine-assistant) | **Assistant Réseau Graphique (GUI)**<br><sub>• Balayage rapide `/24` de chaque sous-réseau</sub><br><sub>• Audit matériel à distance & déploiement SSH</sub><br><sub>• Aucune saisie en ligne de commande requise</sub> |
| ![Bash CLI](https://img.shields.io/badge/Bash_CLI-4EAA25?style=flat-square&logo=gnubash&logoColor=white) | <sub>Script Shell<br>*(Automatisé)*</sub> | <sub>x86-64</sub> | `curl -sSL https://bobine.fit/install.sh \| bash` | **Appliance Dédiée Headless**<br><sub>• Déploiement automatisé en 15 étapes sur Debian 13</sub><br><sub>• Décodage matériel VA-API 4K (&lt; 8% CPU)</sub><br><sub>• Allumage/veille TV par HDMI-CEC & services auto-réparateurs</sub> |
| [![bobine.fit](https://img.shields.io/badge/bobine.fit-4285F4?style=flat-square&logo=data%3Aimage/svg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0OCA0OCIgd2lkdGg9IjQ4IiBoZWlnaHQ9IjQ4Ij48cGF0aCBmaWxsPSIjNENBRjUwIiBkPSJNNDQgMjRjMCAxMS4wNDUtOC45NTUgMjAtMjAgMjAtNC41MiAwLTguNjgtMS41MDMtMTIuMDMtNC4wNDNsOS40NjctMTYuMzk0QTggOCAwIDAgMCAyNCAzMmM0LjQxOCAwIDgtMy41ODIgOC04eiIvPjxwYXRoIGZpbGw9IiNGQkMwMkQiIGQ9Ik00NCAyNEgyNGE4IDggMCAwIDAtNi45MjggNGwtOS40NjcgMTYuMzk0QTE5LjkyIDE5LjkyIDAgMCAxIDQgMjRDNCAxMy45ODcgMTEuMzg1IDUuNzA0IDIxLjAzNiA0LjIyTDMwLjUwMyAyMC42MUE3Ljk3IDcuOTcgMCAwIDAgMzIgMjR6Ii8%2BPHBhdGggZmlsbD0iI0U1MzkzNSIgZD0iTTI0IDRjNy40MDYgMCAxMy44NiA0LjAyNCAxNy4zIDEwLjAyN0wzMC41MDMgMjAuNjFBOCA4IDAgMCAwIDI0IDE2Yy0zLjE1NSAwLTUuOTE0IDEuODI2LTcuMjUgNC40OUw3LjI4NCA0LjA5NUMxMS44OTIgNC4wMzIgMTcuNjUgNCAyNCA0eiIvPjxjaXJjbGUgY3g9IjI0IiBjeT0iMjQiIHI9IjgiIGZpbGw9IiNGRkYiLz48Y2lyY2xlIGN4PSIyNCIgY3k9IjI0IiByPSI2IiBmaWxsPSIjMTk3NkQyIi8%2BPC9zdmc%2B)](https://bobine.fit) | <sub>Portail Web</sub> | <sub>Universel</sub> | [**Visiter bobine.fit**](https://bobine.fit) | **Site Officiel & Documentation**<br><sub>• Guides de démarrage, actualités & notes de version</sub><br><sub>• Documentation interactive & télécommande web</sub> |
| ![GitHub](https://img.shields.io/badge/GitHub-Releases-181717?style=flat-square&logo=github&logoColor=white) | <sub>Binaires & Sources</sub> | <sub>Multi-OS</sub> | [**Voir les Releases GitHub**](https://github.com/FantasmaGlad/Bobine/releases/latest) | **Historique Complet des Versions**<br><sub>• Sommes de contrôle SHA-256 & notes de version</sub> |

---

## Pourquoi Bobine

Les salles de cours collectifs diffusent de plus en plus des cours vidéo pré-enregistrés, animés par un coach à l'écran (« cours virtuels »). Les solutions propriétaires comme Les Mills Cinema ou les plateformes cloud comme Wexer enferment dans une plateforme fermée, un abonnement récurrent par écran et une dépendance critique à Internet. Bobine offre la même expérience en salle — cours planifiés, borne à la demande, expérience adhérent soignée — en gardant le contrôle total :

- **Vous êtes propriétaire.** Vos vidéos, votre matériel, votre planning. Pas d'abonnement, pas de dépendance à un éditeur, pas de compte.
- **Ça marche hors ligne.** Une fois installé, la salle n'a besoin d'aucune connexion internet pour diffuser les cours.
- **Le code est ouvert.** Licence AGPL-3.0, auditable — l'avenir du système ne dépend pas des décisions commerciales d'un éditeur tiers.
- **Ça tourne sur du matériel standard ou bon marché.** Votre ordinateur personnel ou un mini PC d'occasion (type Dell Wyse 5070) suffit — aucune licence récurrente par écran.
- **C'est autonome.** Démarrage automatique à la mise sous tension, reprise après coupure de courant, redémarrage automatique d'un composant en panne.

### Positionnement & Alternatives
- **Alternative aux plateformes fitness propriétaires (Les Mills Cinema, Wexer Virtual, Fitness On Demand, Radical Fitness / catalogues de franchise type Yako)** : Bobine supprime les redevances mensuelles par écran et le verrouillage commercial. Vous restez maître de vos vidéos (cours maison ou libres), de la promotion de vos coachs résidents et de votre grille horaire, avec un fonctionnement 100% hors-ligne sans risque de panne internet.
- **Alternative aux solutions d'affichage dynamique générique (Screenly Anthias, Yodeck, Xibo, TouchPlayer, Waves System)** : Contrairement aux afficheurs passifs limités à des boucles d'images publicitaires, Bobine est conçu pour le métier du fitness : allumage/veille automatique des TV par HDMI-CEC, borne tactile adhérents avec décompte, télécommande coach par QR code local sans application, et radio d'ambiance 24/7 avec annonces vocales programmées sur mini PC Debian 13 avec décodage matériel VA-API (< 8% CPU).

Utilisateurs types : studios, salles de sport, espaces fitness d'hôtels et d'entreprises, kinés et centres de rééducation, studios de danse et de cycling — quiconque diffuse des vidéos de cours planifiées ou à la demande sur un écran, et cherche une alternative souveraine sans abonnement.

Bobine est agnostique aux programmes : les catégories de cours sont libres, il s'adapte donc à n'importe quel catalogue de cours collectifs, cycling, renforcement, mobilité ou bien-être.


---

## Fonctionnalités

- **Planification vidéo** — construisez un planning hebdomadaire ; les cours démarrent automatiquement au bon moment sur le bon écran.
- **Borne cinéma à la demande** — un écran plein écran côté adhérent pour choisir et lancer un cours soi-même, avec animation de lancement et compte à rebours « prochain cours ».
- **Deux sorties d'écran indépendantes** — pilotez un écran câblé (HDMI) et un écran réseau séparément, chacun avec son contenu.
- **Télécommande mobile** — contrôlez la lecture (play, pause, avance, suivant) depuis n'importe quel téléphone du réseau local.
- **Support des télécommandes physiques** — la borne cinéma adhérent et l'écran radio répondent à une télécommande USB à dongle (présentateur / « air remote » média) : flèches et OK pour parcourir et lancer un cours, plus les touches play/pause, piste et volume. Aucun pilote, aucun appairage — la télécommande est vue comme un clavier.
- **Mode coach audio** — diffusez des cours audio sur les enceintes de la salle avec un fond visuel animé ou fixe à l'écran.
- **Radio intégrée** — un lecteur de musique d'ambiance 24/7 façon Spotify, avec fondu enchaîné, aléatoire, répétition et rappels vocaux programmés (« replacez vos poids », etc.).
- **Gestion de bibliothèque simple** — import par glisser-déposer, envoi en lot, catégories libres, sélection groupée, progression fichier par fichier, miniatures automatiques.
- **Local-first et résilient** — reprise automatique après un redémarrage ou une coupure, et un chien de garde qui redémarre un composant mort.
- **Admin web, zéro installation client** — tout s'administre depuis un navigateur ; les écrans adhérents et les télécommandes ne sont que des pages web.
- **Anti-veille Screen Wake Lock API** — empêche la mise en veille intempestive de l'écran pendant les cours et la radio sur tous les navigateurs modernes.

---

## Comment ça marche

Bobine est une machine hôte unique sur votre réseau local qui fait tourner :

- un backend **FastAPI** avec **SQLite** pour le stockage ;
- un kiosque **Chromium** en plein écran (X11) pour l'écran câblé (sur les appliances dédiées) ;
- une interface **Next.js** (admin, borne adhérent, télécommande mobile), servie en pages statiques depuis la même machine.

Les autres écrans (écran réseau, télécommandes, PC d'admin) sont de simples navigateurs pointant vers la machine hôte Bobine. Les médias ne quittent jamais votre réseau.

Pour l'architecture complète, le modèle de données, le contrat réseau et la référence API, voir **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Matériel supporté

Bobine est un logiciel léger, optimisé pour fonctionner avec fluidité sur la quasi-totalité des ordinateurs actuels ou du matériel reconditionné :

- **Ordinateurs portables et PC de bureau (Windows 11 / 10 et Linux)** :
  - PC portables grand public et professionnels : **HP Pavilion**, **Acer Aspire Go**, Lenovo IdeaPad/ThinkPad, Dell Inspiron/Latitude, ASUS Vivobook, etc.
  - Toute tour ou PC de bureau disposant d'au moins 4 Go de mémoire vive (RAM).
- **Gamme Apple Mac (macOS)** :
  - **MacBook Air & MacBook Pro** (puces Apple Silicon M1, M2, M3, M4).
  - **Mac Mini & iMac** (formats particulièrement compacts et silencieux pour la régie d'un studio).
- **Mini PC & Boîtiers compacts (Idéaux pour une diffusion 24/7 en salle)** :
  - Mini PC économiques ou reconditionnés : **Dell Wyse 5070**, **HP ProDesk 400/600 DM**, **Lenovo ThinkCentre Tiny**, **Beelink Mini S12/EQ12**, Intel NUC.
  - Utilisables en application de bureau classique ou en borne dédiée 100% autonome sans écran/clavier (Debian 13).
- **Écrans et diffusion sonore** :
  - N'importe quel téléviseur, moniteur ou vidéoprojecteur raccordé en **HDMI ou DisplayPort**.
  - Écran secondaire optionnel : toute tablette, smart TV ou ordinateur portable doté d'un navigateur web sur le réseau local.
  - Sortie audio jack 3,5 mm, HDMI, carte son USB ou enceinte Bluetooth pour la sono de la salle.

> Pour les détails techniques avancés (accélération matérielle VA-API, empreinte mémoire, schémas de bus et architecture Linux embarquée), consultez la [**Documentation technique (docs/ARCHITECTURE.md)**](docs/ARCHITECTURE.md).

---

## Modes d'installation & de déploiement

Bobine propose différentes méthodes d'installation selon vos besoins et votre profil d'usage :

1. **Option 1 : Application de bureau graphique (La plus simple pour postes de travail et ordinateurs portables)** — Windows 11/10, Linux (Debian/Ubuntu) et macOS (Apple Silicon). S'installe comme un logiciel classique, ouvre automatiquement l'interface web au clic sur l'icône du Bureau, et se loge discrètement dans la barre des tâches / zone de notification.
2. **Option 2 : Appliance Linux dédiée headless (Pour les salles autonomes & la gestion fine)** — Transforme un mini PC dédié (type Dell Wyse 5070) en borne vidéo 24/7 locked-in démarrant directement en kiosque X11 plein écran sans aucun bureau graphique parasite, avec gestion automatique de l'allumage TV par HDMI-CEC. Installation rapide en 1 ligne CLI.
3. **Option 3 : Assistant graphique d'installation Tauri (`assistant/`)** — Un outil de bureau moderne pour découvrir, auditer et déployer à distance vos mini PC via le réseau local en SSH.

---

### Option 1 — Application de bureau graphique (Windows, Linux & macOS)

#### Sur Windows (11, 10 ou Windows IoT)

1. **Téléchargez** [**`Bobine-Setup-3.0.0.exe`**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/Bobine-Setup-3.0.0.exe) (ou depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest)).
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

#### Sur Linux avec bureau (Debian, Ubuntu et dérivés graphiques)

1. **Téléchargez** [**`bobine_3.0.0_amd64.deb`**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/bobine_3.0.0_amd64.deb) (ou depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Installez le paquet** en double-cliquant dessus (Centre d'Applications Ubuntu / GNOME Software) ou en ligne de commande :
   ```bash
   sudo apt install ./bobine_*_amd64.deb
   ```
   *(Toutes les dépendances comme `ffmpeg` sont automatiquement résolues par apt, et les icônes multi-résolution sont intégrées au thème système).*
3. **Lancez Bobine** depuis le raccourci créé sur votre **Bureau**, le menu d'applications ou tapez `bobine` dans un terminal.
   - L'icône Bobine apparaît dans votre zone de notification / barre d'état (tray) et assure la supervision du moteur.
   - Lancement automatique au login XDG configuré nativement.
   - Vos médias et données vivent dans votre dossier utilisateur selon la norme standard XDG : `~/.local/share/bobine/`.

#### Sur macOS (Apple Silicon - M1/M2/M3/M4)

1. **Téléchargez** [**`Bobine-3.0.0.dmg`**](https://github.com/FantasmaGlad/Bobine/releases/download/V3.0.0/Bobine-3.0.0.dmg) (ou depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Ouvrez le .dmg** et glissez `Bobine.app` dans votre dossier **Applications**.
3. **Lancez Bobine** depuis Applications, votre **Bureau** (raccourci créé automatiquement) ou Spotlight.
   - *Premier lancement* : Bobine n'étant pas encore signé via un abonnement Apple payant, Gatekeeper affiche une alerte de sécurité. Ouvrez **Réglages Système → Confidentialité et sécurité**, repérez le message « Bobine a été bloqué », cliquez sur **Ouvrir quand même**, puis confirmez.
   - Dès ce premier lancement, Bobine installe son propre LaunchAgent et démarrera automatiquement à chaque connexion. Une icône dans la barre de menus permet d'ouvrir l'admin, de lancer le mode kiosque plein écran, de redémarrer le backend ou de quitter.
4. **Ouvrez l'interface** : `http://bobine.local` depuis n'importe quel appareil du réseau local (ou `http://127.0.0.1:8000` en local). Les données vivent dans `~/Library/Application Support/Bobine`.

---

### Serveurs Dédiés & Appliances Headless — Méthodes d'Installation Avancées

Pour les studios, salles de fitness et intégrateurs déployant des bornes autonomes 24/7 sur mini PC reconditionné (Dell Wyse 5070, HP ProDesk DM...) sans bureau graphique parasite :

| Méthode | Type | Matériel cible | Déploiement | Points forts & Spécifications |
| :--- | :---: | :---: | :--- | :--- |
| <img src="Assets/Images/bash.svg" width="20" height="20" valign="middle" alt="Bash"> **Installateur Bash (CLI)** | <sub>Script Shell</sub> | <sub>Debian 13 (Mini PC)</sub> | `curl -sSL https://bobine.fit/install.sh \| bash` | <sub>• Séquence automatisée en 15 étapes</sub><br><sub>• Décodage matériel VA-API 4K (&lt; 8% CPU)</sub><br><sub>• Allumage/veille TV par HDMI-CEC</sub><br><sub>• Kiosque X11 plein écran sans veille</sub><br><sub>• Services systemd auto-réparateurs</sub> |
| <img src="Assets/Images/network.svg" width="20" height="20" valign="middle" alt="Réseau"> **Bobine Assistant (Tauri)** | <sub>Application Graphique<br>*(Tauri 2)*</sub> | <sub>Windows, macOS & Linux</sub> | <sub>Assistant GUI par déploiement SSH</sub> | <sub>• Balayage `/24` de chaque interface réseau</sub><br><sub>• Audit matériel en direct (CPU, GPU, RAM, disque)</sub><br><sub>• Orchestration visuelle en 5 étapes guidées</sub><br><sub>• Zéro connaissance en ligne de commande requise</sub> |

#### Option 2 — Appliance Linux dédiée headless (Mini PC / Debian 13)

> **Pour les salles de sport et studios recherchant une indépendance totale, zéro manipulation au quotidien et une gestion matérielle ultra-fine.**  
> Ce mode transforme un mini PC reconditionné (Dell Wyse 5070, HP ProDesk DM, Lenovo Tiny...) en serveur de diffusion vidéo 100% autonome qui démarre directement en affichage kiosque plein écran sans aucun environnement de bureau lourd.

#### 1. Préparation minimale Debian 13
1. **Téléchargez** l'image Debian 13 « Trixie » *netinst* (~700 Mo) sur le site officiel : <https://www.debian.org/download>.
2. **Écrivez-la sur une clé USB** (8 Go et plus) avec [balenaEtcher](https://etcher.balena.io/) ou `dd`.
3. **Démarrez le mini PC sur la clé USB** et déroulez l'installateur : décochez tous les environnements de bureau, ne gardez que **serveur SSH** et **utilitaires usuels**.

#### 2. Installation rapide en 1 ligne de commande (CLI)
Sur le mini PC (en direct ou par SSH), avec votre compte utilisateur normal (pas root) :

```bash
# Installation automatisée en 1 ligne :
curl -sSL https://bobine.fit/install.sh | bash
```

*(Ou manuellement pour un contrôle complet des sources : `git clone https://github.com/FantasmaGlad/Bobine.git && cd Bobine && sudo ./install.sh`).*

**Ce que configure automatiquement `install.sh` :**
- Paquets système : virtualenv Python, Uvicorn, base SQLite, Chromium, FFmpeg avec décodage matériel VA-API.
- Démarrage automatique en session X11 kiosque plein écran avec suppression de toute veille d'écran.
- Automatisation TV HDMI-CEC : allume et éteint automatiquement les téléviseurs aux heures de cours.
- Services systemd supervisés (`bobine-backend.service`, `bobine-kiosk.service`, `bobine-audio-guard.service`).
- Chien de garde (watchdog) de santé : relance automatique en cas d'anomalie et reprise sur coupure de courant.

---

### Option 3 — Assistant graphique d'installation Tauri (`assistant/`)

> **Déployez vos bornes mini PC à distance depuis votre propre poste de travail, sans toucher au terminal.**

Disponible dans le dossier [`assistant/`](assistant/) (compilé nativement pour **Windows**, **Linux** et **macOS**), l'application graphique **Bobine Assistant** guide le déploiement d'une borne de bout en bout :

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
- **Radio** — ouvrez l'écran radio sur un appareil dédié pour diffuser la musique d'ambiance en continu ; pilotage depuis l'onglet *Radio* de l'admin.
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

## Licence

Bobine est un logiciel libre sous licence **GNU Affero General Public License v3.0 (AGPL-3.0)** — voir [`LICENSE`](LICENSE). Si vous exploitez une version modifiée pour fournir un service en réseau, vous devez mettre à disposition le code source correspondant sous la même licence.

---

## État et feuille de route

Bobine est utilisé en production sur du matériel dédié et sur postes de travail de bureau.

Afin de maximiser la portabilité matérielle et d'alléger l'encombrement technique dans les salles et studios, la feuille de route d'ingénierie explore activement l'extension vers des tablettes tactiles autonomes équipées d'une sortie vidéo filaire directe :
* **Tablettes Android avec sortie USB-C DisplayPort** (ex. Xiaomi Pad 6, 7 ou 8, Samsung Galaxy Tab S9/S10) : Embarquement du serveur FastAPI en local via Chaquopy et diffusion vidéo vers l'écran ou le vidéoprojecteur du studio via l'API Presentation d'Android.
* **iPads Apple avec sortie Thunderbolt / USB-C** (ex. iPad Pro à puce M1/M2/M4 avec Thunderbolt / USB 4, iPad Air M2 avec DisplayPort sur USB-C) : Un unique câble ou dock USB-C alimenté relie la tablette au vidéoprojecteur, dédiant l'écran tactile aux commandes de l'instructeur tout en propulsant le flux vidéo du cours sur le grand écran.

Les tickets et contributions sont bienvenus sur le [dépôt GitHub](https://github.com/FantasmaGlad/Bobine).

---

<sub>**Mots-clés :** alternative open source à Les Mills Cinema, alternative à Screenly Anthias pour salle de sport, alternative libre à Wexer Virtual et Fitness On Demand, alternative aux cours vidéo de franchise (Yako, Radical Fitness, Les Mills Virtuel), affichage dynamique fitness auto-hébergé, logiciel de planification de cours collectifs, régie vidéo salle de fitness, lecteur vidéo fitness à la demande, borne de cours virtuels en libre-service, studio de cycling indoor, diffusion vidéo cours coach, thin client, mini PC Dell Wyse 5070, signalétique hors ligne, automatisation TV HDMI-CEC, musique d'ambiance salle de sport, radio fitness avec annonces vocales, local-first, FastAPI, Next.js, assistant d'installation Tauri, application de bureau Windows 11, application de bureau macOS Apple Silicon, paquet Linux Debian Ubuntu .deb, régie vidéo multi-plateforme sans abonnement.</sub>
