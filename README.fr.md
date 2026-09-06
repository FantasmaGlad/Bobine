# Bobine

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="Assets/Images/bobine_banner_dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="Assets/Images/bobine_banner_light.svg">
    <img alt="Bobine" src="Assets/Images/bobine_banner_dark.svg" width="100%">
  </picture>
</p>

**L'alternative open source et auto-hébergée à Les Mills Cinema, Wexer et Screenly Anthias — régie vidéo, affichage dynamique et lecteur planifié hors ligne pour salles de fitness et cours collectifs.**

Bobine transforme n'importe quel PC, Mac ou mini PC dédié bon marché en système vidéo complet pour votre salle : il planifie et diffuse des vidéos de cours collectifs pré-enregistrées sur vos écrans, permet aux adhérents de parcourir et lancer un cours à la demande depuis une borne, pilote un écran câblé et un écran réseau indépendamment, propose un mode coach audio avec fonds animés, et diffuse une musique d'ambiance 24/7. Tout tourne en local, sur votre matériel. Sans cloud, sans abonnement, sans dépendance à un éditeur, sans connexion internet après l'installation.

[Site officiel](https://bobine.fit) · [Documentation web](https://bobine.fit/fr/documentation) · [English](README.md) · [Documentation technique](docs/ARCHITECTURE.md) · [Dernière version](https://github.com/FantasmaGlad/Bobine/releases/latest)

[![CI](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg)](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml)
[![Version : v2.0.1](https://img.shields.io/badge/Release-v2.0.1-brightgreen)](https://github.com/FantasmaGlad/Bobine/releases/latest)
![Licence : AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue)
![Backend : FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![Plateformes : Windows 11 | Debian | Ubuntu | macOS](https://img.shields.io/badge/Platforms-Windows%2011%20%7C%20Linux%20%7C%20macOS-blue)
![Auto-hébergé](https://img.shields.io/badge/Auto--h%C3%A9berg%C3%A9-Local--first-4c1)

---

## ⚡ Téléchargement rapide & Applications de bureau natives

Installez Bobine en quelques secondes comme une application graphique native sur votre poste de travail, ordinateur portable ou PC de régie studio :

| Plateforme | Format | Architecture | Téléchargement direct | Expérience & Fonctionnalités |
| :--- | :---: | :---: | :---: | :--- |
| ![Windows 11](https://img.shields.io/badge/Windows%2011%20%2F%2010-0078D4?style=flat-square&logo=windows11&logoColor=white) | `.exe` (Installeur) | x86-64 | [**Télécharger Bobine-Setup-2.0.1.exe**](https://github.com/FantasmaGlad/Bobine/releases/download/V2.0.1/Bobine-Setup-2.0.1.exe) | Assistant 1 clic, raccourci Bureau, ouverture auto du navigateur, tâche de fond systray, zéro invite de commande |
| ![Debian](https://img.shields.io/badge/Debian-A81D33?style=flat-square&logo=debian&logoColor=white) ![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=flat-square&logo=ubuntu&logoColor=white) | `.deb` (Paquet) | x86-64 (amd64) | [**Télécharger bobine_2.0.1_amd64.deb**](https://github.com/FantasmaGlad/Bobine/releases/download/V2.0.1/bobine_2.0.1_amd64.deb) | Centre d'Applications Ubuntu / `apt install`, conforme XDG, raccourci Bureau unique, zone de notification |
| ![macOS](https://img.shields.io/badge/macOS-000000?style=flat-square&logo=apple&logoColor=white) | `.dmg` (Image disque) | Apple Silicon (arm64) | [**Télécharger Bobine-2.0.1.dmg**](https://github.com/FantasmaGlad/Bobine/releases/download/V2.0.1/Bobine-2.0.1.dmg) | Glisser-déposer `Bobine.app`, icône native Apple Retina `.icns`, icône barre de menus, démarrage auto |
| 🌐 **Toutes les versions** | Binaires & Sources | Multi-OS | [**Voir les Releases GitHub**](https://github.com/FantasmaGlad/Bobine/releases/latest) | Historique complet, notes de version & sommes de contrôle |
| 🌍 **Site officiel** | Portail Web | Universel | [**Visiter bobine.fit**](https://bobine.fit) | Guide de prise en main, actualités & documentation |

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

## En images

Démonstration complète — admin studio, planning, borne adhérent, télécommande mobile et radio — dans les [notes de version 2.0](https://github.com/FantasmaGlad/Bobine/releases/latest).

https://github.com/user-attachments/assets/dfde9250-3016-43cc-af2d-5853f726ffe1

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

## Matériel requis

- Un **ordinateur classique, PC portable, Mac ou mini PC x86-64** :
  - **Modèles Intel recommandés** : Dell Wyse 5070 (Intel Celeron J4105 ~40-50 € reconditionné), HP ProDesk 400/600 G4/G5 DM, Lenovo ThinkCentre M710q/M720q Tiny, Beelink Mini S12/EQ12 (N100/N5105).
  - **Modèles AMD recommandés** : HP EliteDesk 705 G4/G5 Mini (AMD Ryzen 3/5 Pro ~60-80 € reconditionné), Lenovo ThinkCentre M715q/M725q Tiny, HP T630/T730/T740 Thin Client.
  - Tout PC portable ou de bureau sous Windows 10/11, Linux (Debian/Ubuntu/Mint) ou Mac Apple Silicon.
  - Pour les appliances Linux dédiées : GPU Intel (pilote `iHD`/QuickSync) ou AMD (pilote `mesa-va-drivers`/Radeon) avec décodage matériel VA-API configuré automatiquement (< 8% CPU).
- **4 Go de RAM** minimum (8 Go recommandés), SSD de 64 Go à 256 Go selon la taille de votre bibliothèque vidéo.
- **Un ou deux écrans** (HDMI pour la sortie câblée ; l'écran réseau est n'importe quel appareil avec un navigateur).
- Un **réseau local Wi-Fi** (un routeur ou point d'accès) pour joindre les autres appareils — le second écran réseau, la télécommande mobile et le lecteur radio se connectent tous sur le réseau local. Il ne demande **aucune connexion internet** et continue de fonctionner même si votre accès internet tombe : le réseau local seul suffit. Bobine peut aussi tourner **totalement hors ligne, sans aucun réseau**, mais seul l'unique écran câblé (HDMI) est alors utilisé.

Internet n'est nécessaire qu'une seule fois, pour télécharger et installer le logiciel.

---

## Modes d'installation & de déploiement

Bobine propose différentes méthodes d'installation selon vos besoins et votre profil d'usage :

1. **Option 1 : Application de bureau graphique (La plus simple pour postes de travail et ordinateurs portables)** — Windows 11/10, Linux (Debian/Ubuntu) et macOS (Apple Silicon). S'installe comme un logiciel classique, ouvre automatiquement l'interface web au clic sur l'icône du Bureau, et se loge discrètement dans la barre des tâches / zone de notification.
2. **Option 2 : Appliance Linux dédiée headless (Pour les salles autonomes & la gestion fine)** — Transforme un mini PC dédié (type Dell Wyse 5070) en borne vidéo 24/7 locked-in démarrant directement en kiosque X11 plein écran sans aucun bureau graphique parasite, avec gestion automatique de l'allumage TV par HDMI-CEC. Installation rapide en 1 ligne CLI.
3. **Option 3 : Assistant graphique d'installation & Télécommande Tauri (`assistant/`)** — Un outil de bureau moderne pour découvrir, auditer et déployer à distance vos mini PC via le réseau local en SSH, avec télécommande multi-canal intégrée.

---

### Option 1 — Application de bureau graphique (Windows, Linux & macOS)

#### Sur Windows (11, 10 ou Windows IoT)

1. **Téléchargez** [**`Bobine-Setup-2.0.1.exe`**](https://github.com/FantasmaGlad/Bobine/releases/download/V2.0.1/Bobine-Setup-2.0.1.exe) (ou depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest)).
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

1. **Téléchargez** [**`bobine_2.0.1_amd64.deb`**](https://github.com/FantasmaGlad/Bobine/releases/download/V2.0.1/bobine_2.0.1_amd64.deb) (ou depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest)).
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

1. **Téléchargez** [**`Bobine-2.0.1.dmg`**](https://github.com/FantasmaGlad/Bobine/releases/download/V2.0.1/Bobine-2.0.1.dmg) (ou depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest)).
2. **Ouvrez le .dmg** et glissez `Bobine.app` dans votre dossier **Applications**.
3. **Lancez Bobine** depuis Applications, votre **Bureau** (raccourci créé automatiquement) ou Spotlight.
   - *Premier lancement* : Bobine n'étant pas encore signé via un abonnement Apple payant, Gatekeeper affiche une alerte de sécurité. Ouvrez **Réglages Système → Confidentialité et sécurité**, repérez le message « Bobine a été bloqué », cliquez sur **Ouvrir quand même**, puis confirmez.
   - Dès ce premier lancement, Bobine installe son propre LaunchAgent et démarrera automatiquement à chaque connexion. Une icône dans la barre de menus permet d'ouvrir l'admin, de lancer le mode kiosque plein écran, de redémarrer le backend ou de quitter.
4. **Ouvrez l'interface** : `http://bobine.local` depuis n'importe quel appareil du réseau local (ou `http://127.0.0.1:8000` en local). Les données vivent dans `~/Library/Application Support/Bobine`.

---

### Option 2 — Appliance Linux dédiée headless (Mini PC / Debian 13)

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

### Option 3 — Assistant graphique d'installation & Télécommande Tauri (`assistant/`)

> **Déployez et pilotez vos bornes mini PC à distance depuis votre propre poste de travail, sans toucher au terminal.**

Disponible dans le dossier [`assistant/`](assistant/) (compilé nativement pour **Windows**, **Linux** et **macOS**), l'application graphique **Bobine Assistant** offre une orchestration complète à distance :

1. **Découverte automatique sur le réseau** : sonde le réseau local en mDNS (`bobine.local`) et par balayage rapide du sous-réseau `/24` pour localiser vos bornes Bobine.
2. **Déploiement SSH guidé** : connexion sécurisée (clé privée ou mot de passe), audit matériel automatique (CPU, GPU VA-API, RAM, stockage, Wi-Fi), puis exécution de `install.sh` dans un terminal émulé interactif avec barre de progression en temps réel.
3. **Télécommande multi-canal intégrée** : pilotez les 3 canaux de diffusion directement depuis votre poste :
   - **Écran Câblé (HDMI)** : Play, Pause, Stop, Seek, Suivant.
   - **Écran Réseau** : synchronisation et routage du second écran.
   - **Radio d'ambiance** : playlist continue 24/7, réglage du volume et annonces vocales programmées.

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

Bobine est utilisé en production sur du matériel dédié et sur postes de travail de bureau. Prévu : cahiers des charges prospectifs pour tablettes Android tactiles et pupitre coach double-écran sur PC portable. Les tickets et contributions sont bienvenus sur le [dépôt GitHub](https://github.com/FantasmaGlad/Bobine).

---

<sub>**Mots-clés :** alternative open source à Les Mills Cinema, alternative à Screenly Anthias pour salle de sport, alternative libre à Wexer Virtual et Fitness On Demand, alternative aux cours vidéo de franchise (Yako, Radical Fitness, Les Mills Virtuel), affichage dynamique fitness auto-hébergé, logiciel de planification de cours collectifs, régie vidéo salle de fitness, lecteur vidéo fitness à la demande, borne de cours virtuels en libre-service, studio de cycling indoor, diffusion vidéo cours coach, thin client, mini PC Dell Wyse 5070, signalétique hors ligne, automatisation TV HDMI-CEC, musique d'ambiance salle de sport, radio fitness avec annonces vocales, local-first, FastAPI, Next.js, application Tauri, application de bureau Windows 11, application de bureau macOS Apple Silicon, paquet Linux Debian Ubuntu .deb, régie vidéo multi-plateforme sans abonnement.</sub>
