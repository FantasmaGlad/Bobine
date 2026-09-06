# Bobine

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="Assets/Images/bobine_banner_dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="Assets/Images/bobine_banner_light.svg">
    <img alt="Bobine" src="Assets/Images/bobine_banner_dark.svg" width="100%">
  </picture>
</p>

**L'alternative open source et auto-hébergée à Les Mills Cinema, Wexer et Screenly Anthias — régie vidéo, affichage dynamique et lecteur planifié hors ligne pour salles de fitness et cours collectifs.**

Bobine transforme un mini PC dédié bon marché en système vidéo complet pour votre salle : il planifie et diffuse des vidéos de cours collectifs pré-enregistrées sur vos écrans, permet aux adhérents de parcourir et lancer un cours à la demande depuis une borne, pilote un écran câblé et un écran réseau indépendamment, propose un mode coach audio avec fonds animés, et diffuse une musique d'ambiance 24/7. Tout tourne en local, sur votre matériel. Sans cloud, sans abonnement, sans dépendance à un éditeur, sans connexion internet après l'installation.

[Site officiel](https://bobine.fit) · [Documentation web](https://bobine.fit/fr/documentation) · [English](README.md) · [Documentation technique](docs/ARCHITECTURE.md) · [Dernière version](https://github.com/FantasmaGlad/Bobine/releases/latest)

[![CI](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml/badge.svg)](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml)
![Licence : AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue)
![Backend : FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)
![Plateformes : Windows 10/11 | Linux (.deb) | macOS](https://img.shields.io/badge/Platforms-Windows%2010%2F11%20%7C%20Linux%20(.deb)%20%7C%20macOS-blue)
![Auto-hébergé](https://img.shields.io/badge/Auto--h%C3%A9berg%C3%A9-Local--first-4c1)

---

## Pourquoi Bobine

Les salles de cours collectifs diffusent de plus en plus des cours vidéo pré-enregistrés, animés par un coach à l'écran (« cours virtuels »). Les solutions propriétaires comme Les Mills Cinema ou les plateformes cloud comme Wexer enferment dans une plateforme fermée, un abonnement récurrent par écran et une dépendance critique à Internet. Bobine offre la même expérience en salle — cours planifiés, borne à la demande, expérience adhérent soignée — en gardant le contrôle total :

- **Vous êtes propriétaire.** Vos vidéos, votre matériel, votre planning. Pas d'abonnement, pas de dépendance à un éditeur, pas de compte.
- **Ça marche hors ligne.** Une fois installé, la salle n'a besoin d'aucune connexion internet pour diffuser les cours.
- **Le code est ouvert.** Licence AGPL-3.0, auditable — l'avenir du système ne dépend pas des décisions commerciales d'un éditeur tiers.
- **Ça tourne sur du matériel bon marché.** Un thin client ou un mini PC d'occasion (type Dell Wyse 5070) suffit — aucune licence récurrente par écran.
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

---

## Comment ça marche

Bobine est un unique mini PC sur votre réseau local qui fait tourner :

- un backend **FastAPI** avec **SQLite** pour le stockage ;
- un kiosque **Chromium** en plein écran (X11) pour l'écran câblé ;
- une interface **Next.js** (admin, borne adhérent, télécommande mobile), servie en pages statiques depuis la même machine.

Les autres écrans (écran réseau, télécommandes, PC d'admin) sont de simples navigateurs pointant vers le mini PC. Les médias ne quittent jamais votre réseau.

Pour l'architecture complète, le modèle de données, le contrat réseau et la référence API, voir **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Matériel requis

- Un **mini PC ou thin client x86-64** :
  - **Modèles Intel recommandés** : Dell Wyse 5070 (Intel Celeron J4105 ~40-50 € reconditionné), HP ProDesk 400/600 G4/G5 DM, Lenovo ThinkCentre M710q/M720q Tiny, Beelink Mini S12/EQ12 (N100/N5105).
  - **Modèles AMD recommandés** : HP EliteDesk 705 G4/G5 Mini (AMD Ryzen 3/5 Pro ~60-80 € reconditionné), Lenovo ThinkCentre M715q/M725q Tiny, HP T630/T730/T740 Thin Client.
  - Tout PC x86-64 compatible Debian avec un iGPU Intel (pilote `iHD`/QuickSync) ou un APU/GPU AMD (pilote `mesa-va-drivers`/Radeon) convient ; le décodage vidéo matériel VA-API est automatiquement détecté et configuré.
- **4 Go de RAM** minimum (8 Go recommandés), SSD de 64 Go à 256 Go selon la taille de votre bibliothèque vidéo.
- **Un ou deux écrans** (HDMI pour la sortie câblée ; l'écran réseau est n'importe quel appareil avec un navigateur).
- Un **réseau local Wi-Fi** (un routeur ou point d'accès) pour joindre les autres appareils — le second écran réseau, la télécommande mobile et le lecteur radio se connectent tous sur le réseau local. Il ne demande **aucune connexion internet** et continue de fonctionner même si votre accès internet tombe : le réseau local seul suffit. Bobine peut aussi tourner **totalement hors ligne, sans aucun réseau**, mais seul l'unique écran câblé (HDMI) est alors utilisé.

Internet n'est nécessaire qu'une seule fois, pour installer le système d'exploitation et le logiciel.

---

## Installation & Démarrage rapide

Bobine propose désormais deux familles de déploiement adaptées à vos besoins :

1. **L'application de bureau graphique (Recommandée pour un poste classique)** : disponible nativement sur **Windows** (10, 11), **Linux** (`.deb` Debian/Ubuntu) et **macOS** (`.dmg`, Apple Silicon). Bobine s'installe comme un logiciel de bureau traditionnel avec icône dans la zone de notification (systray), supervise le moteur en tâche de fond et permet d'ouvrir l'admin ou d'activer le mode kiosque plein écran en un clic.
2. **L'appliance Linux dédiée headless (Debian 13)** : pour les salles de fitness équipées d'un mini PC dédié (type Dell Wyse 5070) sans bureau graphique, démarrant directement en kiosque X11 plein écran automatique.

---

### Méthode 1 — Application de bureau graphique (Windows, Linux & macOS)

#### Sur Windows (10, 11 ou Windows IoT)

1. **Téléchargez** `Bobine-Setup-*.exe` depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest).
2. **Lancez l'installeur** et suivez l'assistant (choix français/anglais, acceptation de la licence AGPL-3.0). Il installe Bobine dans `Program Files\Bobine`, place un raccourci avec l'icône du projet sur votre **Bureau** et dans le Menu Démarrer, enregistre le lancement automatique de Bobine à l'ouverture de session, et ouvre une règle de pare-feu Windows Defender pour que la télécommande mobile puisse joindre le backend depuis le réseau local.
   - Windows SmartScreen affichera un avertissement « éditeur non reconnu » (l'installeur n'est pas encore signé) : cliquez sur **Informations complémentaires → Exécuter quand même** pour continuer.
3. **Bobine démarre automatiquement** après l'installation : une icône apparaît dans la zone de notification. Cliquez dessus pour ouvrir l'admin, lancer la fenêtre en mode kiosque plein écran, redémarrer le backend ou quitter.
4. **Ouvrez l'interface** : `http://bobine.local` depuis n'importe quel appareil du réseau local (ou `http://127.0.0.1:8000` sur le PC lui-même). Les données applicatives (vidéos, base SQLite, logs) vivent sous `%ProgramData%\Bobine`.

#### Sur Linux avec bureau (Debian, Ubuntu et dérivés graphiques)

1. **Téléchargez** le paquet `bobine_*_amd64.deb` depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest).
2. **Installez le paquet** en terminal ou via votre logithèque :
   ```bash
   sudo apt install ./bobine_*_amd64.deb
   ```
   *(Toutes les dépendances comme ffmpeg sont automatiquement résolues par apt, et les icônes multi-résolution sont intégrées au thème hicolor).*
3. **Lancez Bobine** depuis le raccourci créé sur votre **Bureau**, le menu d'applications ou tapez `bobine` dans un terminal.
   - L'icône Bobine apparaît dans votre zone de notification / barre d'état (tray) et assure la supervision du moteur.
   - Lancement automatique au login XDG configuré nativement (et unité systemd utilisateur `systemctl --user start bobine` disponible — utilisez l'un ou l'autre, pas les deux à la fois, pour éviter de faire tourner deux instances).
   - Vos médias et données vivent dans votre dossier utilisateur selon la norme XDG : `~/.local/share/bobine/`.

#### Sur macOS (Apple Silicon)

1. **Téléchargez** `Bobine-*.dmg` depuis la [dernière release GitHub](https://github.com/FantasmaGlad/Bobine/releases/latest).
2. **Ouvrez le .dmg** et glissez `Bobine.app` (dotée de son icône Apple native Retina `.icns`) dans votre dossier **Applications**.
3. **Lancez Bobine** depuis Applications, votre **Bureau** (raccourci créé automatiquement) ou Spotlight.
   - Bobine n'étant pas encore signé, Gatekeeper bloque le premier lancement : ouvrez **Réglages Système → Confidentialité et sécurité**, repérez le message « Bobine a été bloqué », cliquez sur **Ouvrir quand même**, puis confirmez.
   - Dès ce premier lancement, Bobine installe son propre LaunchAgent et démarrera automatiquement à chaque connexion par la suite. Une icône dans la barre de menus permet d'ouvrir l'admin, de lancer la fenêtre en mode kiosque plein écran, de redémarrer le backend ou de quitter.
4. **Ouvrez l'interface** : `http://bobine.local` depuis n'importe quel appareil du réseau local. Les données applicatives (vidéos, base de données, logs) vivent sous `~/Library/Application Support/Bobine`.

---

### Méthode 2 — Appliance Linux headless dédiée (Debian 13 sur mini PC)

Ce mode transforme un mini PC dédié (sans écran clavier au quotidien) en serveur de diffusion vidéo 100% autonome et verrouillé en affichage kiosque.

#### 1. Installer Debian 13 depuis une clé USB
Bobine vise **Debian 13 « Trixie »**, installation minimale, sans environnement de bureau (Bobine apporte sa propre pile d'affichage kiosque).

1. **Téléchargez** l'image Debian 13 *netinst* (~700 Mo) sur le site officiel : <https://www.debian.org/download>.
2. **Écrivez-la sur une clé USB** (8 Go et plus) avec [balenaEtcher](https://etcher.balena.io/) ou `dd`.
3. **Démarrez le mini PC sur la clé USB** et déroulez l'installateur : décochez tous les environnements de bureau, ne gardez que **serveur SSH** et **utilitaires usuels**.

#### 2. Installer Bobine en ligne de commande
Sur le mini PC (en direct ou par SSH), avec votre compte normal (pas root) :

```bash
# Installation rapide en 1 ligne :
curl -sSL https://bobine.fit/install.sh | bash
```

*(Ou manuellement : `git clone https://github.com/FantasmaGlad/Bobine.git && cd Bobine && sudo ./install.sh`).*

---

### Méthode 3 — Assistant graphique d'installation & Télécommande (Poste admin distant)

Pour déployer vos mini PC sans taper une seule commande terminal, l'application graphique **Bobine Assistant** dans [`assistant/`](assistant/) (compatible **Linux**, **Windows** et **macOS**) permet de tout orchestrer à distance :
1. **Découverte automatique** : localise les mini PC sur votre réseau local via mDNS (`bobine.local`) ou balayage rapide du sous-réseau.
2. **Déploiement SSH piloté** : connexion sécurisée (clé privée ou mot de passe), audit matériel automatique (CPU, GPU VA-API, RAM, stockage, Wi-Fi), puis déroulement de `install.sh` avec session PTY et journal en direct.
3. **Télécommande de bureau intégrée** : pilotez les canaux de diffusion (Câblé HDMI, Écran Réseau, Radio d'ambiance) directement depuis votre poste admin (Play, Pause, Stop, Volume, Seek).

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

Bobine est utilisé en production sur du matériel dédié. Prévu : un assistant d'installation graphique (fondations CLI déjà en place), un site web dédié et une documentation étendue. Les tickets et contributions sont bienvenus sur le [dépôt GitHub](https://github.com/FantasmaGlad/Bobine).

---

<sub>**Mots-clés :** alternative open source à Les Mills Cinema, alternative à Screenly Anthias pour salle de sport, alternative libre à Wexer et Fitness On Demand, alternative aux cours vidéo de franchise (Yako, Radical Fitness), affichage dynamique fitness auto-hébergé, logiciel de planification de cours collectifs, lecteur vidéo fitness à la demande, borne de cours virtuels, studio de cycling indoor, régie vidéo salle de sport, thin client, mini PC Dell Wyse 5070, signalétique hors ligne, automatisation TV HDMI-CEC, local-first, FastAPI, Next.js, application de bureau Windows, application de bureau macOS, paquet Linux .deb, régie vidéo multi-plateforme.</sub>
