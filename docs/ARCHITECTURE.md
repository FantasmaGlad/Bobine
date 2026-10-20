# Bobine — Architecture technique & référence développeur

> **Bilinguisme** : ce document doit être maintenu en parallèle de sa version anglaise ([`ARCHITECTURE.en.md`](ARCHITECTURE.en.md)) — dernière synchronisation : 2026-09-13.

> Référence technique. Pour une présentation orientée utilisateur (à quoi sert Bobine, installation guidée, prise en main), voir le **[README](../README.md)** (`README.fr.md` pour le français).

Diffusion, planification et pilotage de vidéos de cours en salle, sur mini PC dédié. Serveur FastAPI mono-processus + SQLite, kiosque Chromium X11, interface d'administration et télécommande mobile Next.js.

Ce document est écrit pour quiconque souhaite **comprendre, exploiter, modifier ou déployer** le système Bobine : il décrit l'architecture réellement en place (pas une intention), le contrat réseau, le modèle de données, ainsi que la configuration d'exploitation sur mini PC dédié.

---

## Sommaire

1. [Stack et démarrage](#1-stack-et-démarrage)
2. [Architecture générale](#2-architecture-générale)
3. [Modèle de données & Persistance SQLite](#3-modèle-de-données--persistance-sqlite)
3bis. [Pipeline d'importation, Accélération Matérielle Multi-OS & Annulation Réactive](#3bis-pipeline-dimportation-accélération-matérielle-multi-os--annulation-réactive)
3ter. [Télémétrie Matérielle Universelle Multi-OS & Métriques d'Assiduité](#3ter-télémétrie-matérielle-universelle-multi-os--métriques-dassiduité)
4. [Canaux de diffusion & Gestionnaire de lecture](#4-canaux-de-diffusion--gestionnaire-de-lecture)
5. [Module Radio](#5-module-radio)
5bis. [Périphériques (audio, Bluetooth, Wi-Fi)](#5bis-périphériques-audio-bluetooth-wi-fi)
6. [Mode Audio Coach & Fonds animés](#6-mode-audio-coach--fonds-animés)
7. [Script d'installation & Services systemd](#7-script-dinstallation--services-systemd)
8. [Référence API HTTP & WebSockets](#8-référence-api-http--websockets)
9. [Exploitation & Découverte Réseau (Wyse)](#9-exploitation--découverte-réseau-wyse)
10. [Matrice des interfaces & compatibilité multi-plateforme](#10-matrice-des-interfaces--compatibilité-multi-plateforme)
11. [Licence](#11-licence)

---

## 1. Stack et démarrage

### Stack technique

- **Backend** : Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/) + `uvicorn` (mono-processus, cf. §2), [SQLAlchemy](https://www.sqlalchemy.org/), SQLite (`data/database.db`), `APScheduler` (planification), `watchdog` (surveillance des dossiers d'import), `ffmpeg` avec **accélération matérielle multi-OS** (`h264_mediacodec` sur Android, `h264_videotoolbox` sur macOS Apple Silicon/Intel, `h264_vaapi` sur Linux avec pilote Intel QuickSync ou AMD Mesa, `h264_qsv` sur Windows avec pilote Intel QuickSync, repli universel `libx264`), Web Audio API (crossfade radio, côté navigateur). Politique stricte de conservation intégrale des flux 2K et 4K sans sous-échantillonnage.
- **Frontend** : [Next.js](https://nextjs.org/) 16 (App Router, export statique servi par le backend en production), React 19, TypeScript, CSS Vanilla (global + design tokens, **16 thèmes de couleurs** commutables à chaud via `:root[data-theme=…]`, dont la paire minérale « Charbon » / « Charbon Sombre » certifiée WCAG AA/AAA, design system Apple Glassmorphism avec flou spéculaire de 28px, micro-interactions tactiles haptiques et bordures dynamiques à fort contraste, accordéons de navigation latérale mutuellement exclusifs et grille Bento asymétrique pour les actions directes), PWA (`manifest.json`), WebSockets, glisser-déposer natif (HTML5), Web Audio API.
- **Exploitation & Kiosque** : Debian 13 (Trixie), Chromium en mode kiosque (X11 / `xinit`), `systemd` (services backend, kiosque, garde audio, chien de garde), `avahi-daemon` (découverte mDNS).
- **Portabilité Android (`android/`)** : application native Android (Kotlin + CPython embarqué via [Chaquopy](https://chaquopy.com/)), `minSdk 34` / `targetSdk 36` (Android 14-16, API 36 / Xiaomi Pad 8). Double affichage matériel via `DisplayManager` et `Presentation` (écran tactile sur `/grid` sans sidebar, sortie HDMI externe via dock USB-C sur `/cinema` avec écran de veille « En attente d'un cours »), `ForegroundService` persistant, binaires ARM64 NDK r28c (`ffmpeg`/`ffprobe` Bionic natifs, 16 KB page size) avec décodage matériel `av1_mediacodec` et encodage `h264_mediacodec` ultra-rapide.
- **Installation & outils** : `install.sh` (**Bash** idempotent : détection matérielle dynamique, remédiation APT, `--as-user`, sortie machine `--progress=json`, §7) ; **assistant d'installation graphique** (`assistant/`, application de bureau **Tauri / Rust**, balayage `/24` de chaque interface réseau locale et orchestration SSH — cf. [`assistant/README.md`](../assistant/README.md)).

**Langages du dépôt** : **Python** (backend FastAPI), **TypeScript/React** (frontend Next.js), **Kotlin** (application Android), **Bash** (`install.sh`), **Rust** (cœur de l'assistant d'installation). **Intégration continue** (GitHub Actions, `.github/workflows/ci.yml`) à chaque push/PR : build du frontend, contrôle de syntaxe du backend, `cargo clippy` + `cargo test` de l'assistant, build et signature APK Android, et sanity de `install.sh` (syntaxe + cohérence du compteur d'étapes).

### Développements locaux

**Préréquis** : Node.js ≥ 20, Python ≥ 3.11.

```bash
# 1. Backend (FastAPI) — port 8001 en dev (voir note ci-dessous)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 2. Frontend (Next.js)
cd frontend
npm install
npm run dev             # accessible sur http://localhost:3000
```

> **Quirk de dev (port)** : servi par `next dev` sur `:3000`, le frontend route ses appels API/WebSocket vers `localhost:8001` (cf. `getApiUrl`/`getWsUrl`) — d'où le backend sur **8001** en développement. Alternative sans ce décalage, pratique pour vérifier le rendu réel : `cd frontend && npm run build` (export statique dans `frontend/out`) puis lancer le backend sur `:8000` — il sert lui-même `frontend/out` à `/` (même origine `/api`), il suffit alors de naviguer sur `http://localhost:8000/<route>/`.

**Validation rapide avant commit** :

```bash
# Vérification de syntaxe Python (AST)
backend/.venv/bin/python -c "import ast; ast.parse(open('backend/app/main.py').read())"

# Vérification du typage Frontend (TypeScript)
cd frontend && npx tsc --noEmit

# Tests du cœur de l'assistant d'installation (Rust) — mêmes checks qu'en CI
cd assistant && cargo test --workspace
```

### Configuration (`config.toml`)

La configuration est chargée selon l'ordre de priorité suivant :
1. Variables d'environnement préfixées `BOBINE_` (priorité maximale).
2. `/etc/bobine/config.toml` (production, écrit par `install.sh`).
3. `config.toml` à la racine du dépôt (développement).

| Clé | Défaut | Rôle |
|---|---|---|
| `database.database_url` | `sqlite:///data/database.db` | URL de connexion SQLite |
| `media.media_dir` | `data/videos` | Stockage des vidéos importées |
| `media.watch_dir` | `data/watched` | Dossier surveillé pour import automatique |
| `server.host` / `port` | `0.0.0.0:8000` | Écoute HTTP du backend |
| `playback.wait_time_between_courses` | `0` | Délai d'inter-cours (s) |
| `playback.volume_default` | `100` | Volume par défaut (0-100) |

> **Fichiers temporaires d'upload** : le backend force `tempfile.tempdir` sur `data/tmp` (à côté des médias) au démarrage, au lieu de `/tmp`. Sur le Wyse, `/tmp` est un tmpfs en RAM (~3,8 Go) qu'un gros import vidéo/audio saturait (`OSError: No space left on device`, remonté côté client en « There was an error parsing the body ») alors que le disque média a des dizaines de Go libres.

---

## 2. Architecture générale

```
┌─────────────┐      HTTP / WebSockets      ┌─────────────────────────────────┐
│  Frontend   │ ───────────────────────────►│        Backend FastAPI          │
│  Next.js    │                             │    (uvicorn, mono-processus)    │
│ (Kiosque /  │◀─────────────────────────── │  app/routers/* → playback_mgr   │
│  Admin /    │                             └─────────────────────────────────┘
│ Mobile Remote)│                                    │
└─────────────┘                                    │
                                                   ▼
                                          ┌──────────────┐
                                          │    SQLite    │
                                          │ (database.db)│
                                          └──────────────┘
```

Le backend tourne en un seul processus `uvicorn` (`--workers 1`). L'état de lecture (position, playlist, planning) vit directement en mémoire de ce processus et est diffusé aux clients connectés via WebSocket ; aucun bus d'état externe n'est nécessaire pour rester synchronisé.

> **Historique (avant le passage en mono-processus)** : le backend tournait avec 4 workers `uvicorn` sous le même processus maître, et Redis servait de bus d'état partagé (position de lecture, verrous de tick, synchronisation de planning) et de canal Pub/Sub inter-workers — chaque worker exécutant sa propre copie du `lifespan` et de l'`AsyncIOScheduler`, une action à effet de bord (auto-démarrage radio, déclenchement d'une programmation) devait être protégée par un verrou distribué pour n'avoir lieu qu'une fois. Le passage au mono-processus supprime cette classe entière de problèmes par construction : il n'existe plus qu'une seule copie de chaque état, plus de course entre workers à arbitrer.

### Arborescence backend (`backend/app/`)

- `main.py` : Entrée de l'application FastAPI, initialisation des routes, des événements de démarrage (`boot_state.py`) et du serveur d'assets statiques.
- `playback_manager.py` : Moteur de lecture multi-canal câblé/réseau (gestion de l'état `PLAYING`, `PAUSED`, `IDLE`, minutage et reprise).
- `radio_manager.py` : Moteur de lecture du canal Radio (§5) — état INDÉPENDANT de `playback_manager.py` (playlist de morceaux, pas vidéo/cours), même connexion WebSocket.
- `scheduler_manager.py` : Gestionnaire `APScheduler` de la programmation horaire (récurrences, détections de conflits, décalages, fenêtres radio).
- `models.py` : Déclarations SQLAlchemy ORM.
- `config.py` : Gestionnaire de configuration dynamique.
- `routers/` : Endpoints HTTP groupés par domaine (`videos`, `backgrounds`, `playlists`, `audio`, `audio_playlists`, `schedule`, `playback`, `settings`, `logs`, `import_jobs`, `radio`, `radio_playlists`, `radio_announcements`, `devices`) ; `devices/` : interface de pilote et pilotes Linux, sidecar, Android, PIN et service (§5bis).

---

## 3. Modèle de données & Persistance SQLite

Le schéma de données est géré par **SQLAlchemy**. Il n'y a **pas d'Alembic actif** dans ce projet (le dossier `alembic/versions/` n'existe pas : seuls `alembic.ini`, `alembic/env.py` et `alembic/README` sont présents) : les tables sont créées par `Base.metadata.create_all()` au démarrage, et l'ajout de colonnes sur des tables existantes passe par des micro-migrations idempotentes dans `database.py::_migrate_add_missing_columns`. Stockage dans un fichier SQLite unique (`data/database.db`).

### Entités principales

- `videos` / `backgrounds` : Métadonnées des médias (durée, résolution, codec, description/synopsis, fps, bitrate, canaux audio et codec audio, vignettes générées dans `data/thumbnails`).
- `video_subtitles` : Sous-titres multilingues associés aux cours vidéo (`video_id`, `language_code`, `language_label`, `file_path`, `format`), stockés en WebVTT standardisé (`data/subtitles/`) avec conversion automatique des fichiers `.srt` importés.
- `playlists` & `playlist_items` : Playlists de cours vidéo ordonnées.
- `audio_courses` & `audio_tracks` : Cours audio importés et leurs pistes associées.
- `audio_playlists` & `audio_playlist_items` : Éditions mixées audio coach avec attribution de fond visuel par piste.
- `schedules` & `schedule_overrides` : Programmations récurrentes ou ponctuelles, avec gestion des exceptions d'occurrences (annulation, remplacement).
- `playback_state` : État de lecture persisté par canal (*Câblé* et *Réseau*), incluant la sauvegarde des actions interrompues pour la reprise automatique.
- `playback_sessions` : Sessions d'assiduité et d'écoute par canal et type de lancement, durée jouée, durée totale et statut d'achèvement (`completed = True` si progression ≥ 90%).
- `course_ratings` : Évaluations de satisfaction 5 étoiles (score 1 à 5) recueillies sur le pupitre coach `/grid` ou grand écran `/cinema` avec horodatage UTC et canal.
- `settings` : Clés/valeurs des paramètres modifiables à chaud depuis l'interface admin.
- `activity_log` : Journal des événements fonctionnels et techniques du système.
- `radio_tracks`, `radio_tags`, `radio_playlists` & `radio_playlist_items` : Bibliothèque musicale et playlists du module Radio (§5) — sous-système indépendant des cours vidéo/audio coach.
- `radio_announcements` & `radio_announcement_rules` : Rappels de bienséance (annonces) et leurs règles de déclenchement.

---

## 3bis. Pipeline d'importation, Accélération Matérielle Multi-OS & Annulation Réactive

Bobine intègre un pipeline de traitement et d'ingestion multimédia unifié couvrant 4 flux d'importation distincts : les **vidéos de cours** (`/api/videos/upload` ou dossier `data/watched`), les **fonds animés** (`/api/backgrounds/upload` ou dossier `data/backgrounds_watched`), les **cours audio coach** (`/api/audio/upload` ou dossier `data/audio_watched`), et les **morceaux radio** (`/api/radio/upload` ou dossier `data/radio_watched`).

### 1. File d'attente centralisée & Télémétrie en temps réel (`import_jobs.py`)

Toute importation déclenchée par upload web ou par le surveillant de fichiers (`watchdog` / `PollingObserver`) génère un job unique suivi dans `app/utils/import_jobs.py` :
- **États successifs** : `uploading` → `normalizing` (ou `transcoding`) → `thumbnail` → `done` (ou `error` / `cancelled`).
- **Télémétrie continue FFmpeg** : invocation avec `-progress pipe:1 -nostats`. Un thread d'arrière-plan dédié consomme `stderr` en continu pour prévenir tout blocage de buffer. L'avancement extrait en direct la vitesse de conversion (`speed`, ex. `4.2x`), le pourcentage d'avancement (`progress_percent`) et l'estimation de durée restante (`eta_seconds`).
- **Consultation API** : `GET /api/import-jobs` expose la liste ordonnée des jobs actifs et terminés récents avec leur progression détaillée pour le polling de l'interface d'administration.

### 2. Accélération matérielle multi-OS intégrale (`video_utils.py`)

Le moteur de normalisation exploite un pipeline d'accélération matérielle complet à 3 paliers automatiques (Full Hardware direct VRAM → Hybride GPU → Repli CPU) adapté dynamiquement au profil système (`get_deployment_profile()`) et au silicium graphique :
- **Linux Bureau & Appliance Wyse (Intel QuickSync / AMD VA-API)** : Palier 1 Full HW via détection automatique du nœud de rendu DRM (`_find_vaapi_device()`), décodage direct en surfaces VA-API (`-hwaccel vaapi -hwaccel_output_format vaapi`), formatage GPU `scale_vaapi=format=nv12` et encodage matériel `h264_vaapi`. Traitement 100% interne à la VRAM sans transit RAM-PCIe, réduisant la charge CPU de plus de 93% (élimination des pics de 30W). En cas de flux non géré, bascule automatique vers le Palier 2 Hybride (`-vf "format=nv12,hwupload"`).
- **Android (SoC Qualcomm Snapdragon / MediaTek)** : Décodage matériel proactif cadencé par `-operating_rate 1000 -c:v <codec>_mediacodec` (AV1, HEVC, VP9, H.264) et encodage matériel natif `h264_mediacodec` (`-pix_fmt nv12 -b:v <bitrate>`). Vitesse constatée sur tablette Xiaomi Pad 8 : de **4.2x à 5.1x** temps réel.
- **macOS (Apple Silicon M1 à M4 & Intel)** : Décodage matériel direct `-hwaccel videotoolbox` et encodage matériel `h264_videotoolbox` (`-q:v 65 -pix_fmt yuv420p`), conversion ultra-rapide sans solliciter les cœurs CPU.
- **Windows (Intel QuickSync)** : Décodage matériel `-hwaccel qsv -hwaccel_output_format qsv` et encodage `h264_qsv` (`-preset fast`).
- **Repli universel (Palier 3)** : si l'accélération matérielle échoue ou n'est pas disponible (ex. serveur headless sans GPU), repli automatique transparent sur `libx264 -preset veryfast` sans interruption de la tâche.
- **Intervalle de trames clés resserré** : toutes les vidéos normalisées (quel que soit l'encodeur) reçoivent `-g 60` (`-keyint_min 60` en repli logiciel), soit une trame clé toutes les ~2s à 30 im/s — garantit une avance/retour rapide fiable et évite qu'un seek admin vers une position hors keyframe ne laisse le décodeur bloqué (cf. §4, « Récupération d'un décodeur vidéo bloqué »).

### 3. Règle d'or : Conservation intégrale de la qualité source (Zéro dégradation)

Bobine respecte strictement la fidélité des médias sources :
- **Aucun sous-échantillonnage destructif** : les résolutions natives 2K (1440p) et 4K (2160p) ne sont jamais réduites en 1080p.
- **Débits cibles adaptatifs haute fidélité** (`_get_target_bitrate`) :
  - **4K UHD (≥ 2160p)** : 28 Mbps (bitrate max 35 Mbps)
  - **2K QHD (≥ 1440p)** : 14 Mbps (bitrate max 18 Mbps)
  - **1080p FHD (≥ 1080p)** : 6 Mbps (bitrate max 8 Mbps)
  - **720p HD** : 3.5 Mbps (bitrate max 4.5 Mbps)

### 4. Annulation réactive & Nettoyage atomique

- **Arrêt immédiat** : un clic sur la croix (✕) dans le panneau flottant d'upload émet un appel `DELETE /api/import-jobs/{job_id}`.
- **Interruption du processus** : `cancel_job()` signale l'annulation atomique, envoie un signal `SIGTERM` (puis `SIGKILL` de sécurité sous 1.5s) au sous-processus FFmpeg enregistré, et annule le `Future` du pool de threads.
- **Purge intégrale** : l'interruption lève `JobCancelledError`, entraînant la suppression immédiate des fichiers de destination partiels (`dest_path`, miniatures temporaires) sans aucune écriture en base de données.
- **Nettoyage préventif au démarrage** : le backend scanne les répertoires médias au lancement pour supprimer les reliquats temporaires orphelins laissés par une coupure d'alimentation brutale.

### 5. Estimation de durée avant démarrage & file d'attente (`encode_speed_stats.py`)

La télémétrie FFmpeg du §1 (`progress_percent`, `eta_seconds`, `speed`) n'existe qu'une fois le réencodage réellement démarré — les étapes qui précèdent (attente en file, analyse du fichier, copie) n'affichaient auparavant qu'un indicateur « en cours » sans durée. Deux estimations complètent désormais cette télémétrie :
- **Estimation initiale par tâche** (`estimated_seconds`) : posée dès la fin de l'analyse du fichier (avant le lancement de FFmpeg), calculée à partir de la durée de la vidéo source divisée par une vitesse moyenne (`x` temps réel) observée historiquement pour le couple (encodeur matériel, palier de résolution 4K/2K/1080p) courant. Cette moyenne mobile est persistée dans la table `settings` (clé `encode_speed_stats:<encodeur>:<palier>`) et affinée après chaque réencodage réussi ; tant qu'aucun échantillon n'existe, un repère par défaut prudent est utilisé par encodeur. Purement indicative, elle est écrasée par `eta_seconds` dès que la progression FFmpeg réelle démarre.
- **Estimation cumulée de file d'attente** (`queue_eta_seconds`) : pour une tâche donnée, somme du temps restant estimé (ETA en direct si déjà en cours de réencodage, sinon estimation initiale) de toutes les tâches non terminées placées avant elle, plus son propre temps restant. Calculée dans `list_jobs()`, au même titre que `queue_position` — une estimation, pas une garantie.

Ces deux champs sont exposés par `GET /api/import-jobs` et affichés dans le panneau flottant d'upload (`UploadManager.tsx`) : `~X min (estimation)` pendant l'analyse/la copie, puis `(N devant, ~X min au total)` tant qu'une tâche attend son tour.

---

## 3ter. Télémétrie Matérielle Universelle Multi-OS & Métriques d'Assiduité

### 1. Supervision Matérielle Universelle (`hardware_info.py`)

Bobine embarque un module d'introspection matérielle de bas niveau (`backend/app/utils/hardware_info.py`) exposé par `GET /api/settings/system` et consommé par le panneau Réglages (`/settings`) et le tableau de bord (`/metrics`). Afin de garantir une restitution fidèle et professionnelle (sans codes techniques bruts, sans architecture générique `aarch64` ni étiquettes vagues), le module résout les dénominations commerciales complètes et audite les composants physiques réels sur les 5 profils d'exécution :

- **Processeur (CPU)** :
  - *Android ARM64* : lecture des propriétés système AOSP `ro.soc.model` (ex: `Snapdragon 8 Elite`, `Dimensity 9300`) et repli sur `ro.board.platform` ou `/proc/cpuinfo`.
  - *Linux Bureau & Wyse Headless* : extraction du modèle commercial depuis `/proc/cpuinfo` (`model name`), nettoyage regex des suffixes superflus (`(R)`, `(TM)`, fréquences redondantes).
  - *macOS Desktop* : appel `sysctl -n machdep.cpu.brand_string` (ex: `Apple M3 Pro`, `Intel Core i7`).
  - *Windows Desktop* : requête directe dans le Registre Windows `HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0\ProcessorNameString` (ultra-rapide, sans spawn de processus).
- **Puce Graphique (GPU)** :
  - *Android ARM64* : identification de la puce Adreno via les nœuds sysfs du pilote graphique Qualcomm `/sys/class/kgsl/kgsl-3d0/gpu_model` (ex: `Qualcomm Adreno 825`), ou nœuds Mali pour SoC MediaTek.
  - *Linux Bureau & Wyse Headless* : parcours sysfs DRM `/sys/class/drm/card*/device/` avec résolution du nom via `udevadm` ou extraction `lspci` (Intel UHD/Iris Xe, AMD Radeon Graphics, Nvidia GeForce) avec nettoyage des parenthèses vides.
  - *macOS Desktop* : interrogation `system_profiler SPDisplaysDataType`.
  - *Windows Desktop* : requête PowerShell `Get-CimInstance Win32_VideoController` non bloquante avec timeout strict (1,5s).
- **Mémoire Vive (RAM)** :
  - Restitution de la capacité totale et utilisée (en Go et %), ainsi que des métadonnées constructeur : marque/fabricant (Samsung, Micron, SK Hynix, Crucial, Corsair), technologie de mémoire (LPDDR5X, LPDDR5, DDR5, DDR4, LPDDR4X) et fréquence d'horloge maximale (ex: 8533 MT/s, 6400 MHz).
  - *Android* : diagnostic via `/proc/meminfo`, propriétés de plateforme et sysfs mémoire.
  - *Linux / Wyse* : inspection SMBIOS non-root via `udevadm info -p /devices/virtual/dmi/id` ou `dmidecode -t memory` si disponible.
  - *macOS* : `system_profiler SPMemoryDataType`.
  - *Windows* : requête WMI `Win32_PhysicalMemory` (Manufacturer, SMBIOSMemoryType, Speed).
- **Stockage Principal** :
  - Identification commerciale du disque système (ex: `Samsung SSD 990 PRO 2TB`, `Western Digital WD Black SN850X`, `Stockage Flash UFS 4.0 256 Go` sous Android).
  - Calcul de l'espace total, libre et pourcentage d'occupation via `shutil.disk_usage()` (ou `StatFs` sous Android).
  - *Linux / Wyse* : nœuds sysfs `/sys/block/<disk>/device/model` et `lsblk`.
  - *Android* : inspection du type de bus eMMC / UFS (`/sys/block/sda/device/model` ou `mmcblk0`).
- **Puissance Électrique en Watts (W) & Énergie Cumulée (Wh)** :
  - Mesure instantanée de la consommation électrique globale en direct :
  - *Linux x86 / Wyse* : lecture de l'interface Intel/AMD RAPL (Running Average Power Limit) sous `/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` avec échantillonnage différentiel sur 100 ms.
  - *Laptops / Tablettes / Macs sur batterie* : calcul instantané `P = U * I` via les capteurs de batterie (sysfs `/sys/class/power_supply/`, `AppleSmartBattery` sous macOS via `ioreg`).
  - *Sur secteur (maintien batterie et chargeur AC)* :
    - Sur Linux laptop : priorisation des capteurs matériels APU/GPU/SoC (`hwmon` `amdgpu` ou RAPL) sur la sonde de batterie `BAT1` (qui rapporterait un faux courant de fuite de 0.05 W une fois la batterie pleine).
    - Sur Android (Chaquopy) : détection de l'état branché (`plugged > 0` ou statut `CHARGING`/`FULL`). En maintien à 100%, le courant chimique aux bornes de la batterie étant de 0 µA, la puissance active réelle est calculée à partir du profil thermique/énergétique du SoC et du scaling de charge CPU instantanée (3.2W de base + scaling CPU dynamique).
    - Sur macOS : détection via `ioreg -rc AppleSmartBattery` (`Watts` direct ou `ExternalConnected`).
    - Sur Windows : interrogation de l'état AC via `Get-CimInstance Win32_Battery`.
  - *Énergie Cumulée & Puissance Moyenne* : intégration trapézoïdale continue de la puissance instantanée au fil du temps (`cumulative_energy_wh = ∫ P dt`), exposée en Watt-heures (Wh) aux côtés de la puissance moyenne (`average_power_watts`).
- **Températures CPU et GPU (°C)** :
  - Lecture des capteurs thermiques matériels sous `/sys/class/thermal/thermal_zone*` et `/sys/class/hwmon/`.
  - Sous Android, ciblage spécifique des zones CPU et GPU Adreno `/sys/class/kgsl/kgsl-3d0/temp`.
- **Temps d'activité (Uptime & Runtime)** :
  - Uptime du système d'exploitation et runtime continu du serveur Bobine (depuis l'initialisation de l'instance FastAPI).

### 2. Moteur de Métriques d'Assiduité, Télémétrie Système & Rétention (`/metrics`)

- **Découplage Modulaire de l'Interface (`/metrics`)** :
  - La section Métriques est découpée en deux espaces distincts et ergonomiques :
    - **Cours & Assiduité (`/metrics/courses`)** : KPIs de séances, taux de complétion, durée de visionnage, histogramme d'affluence horaire 24h et palmarès des cours les plus suivis et les mieux notés.
    - **Système & Matériel (`/metrics/system`)** : surveillance en direct de la machine (CPU, RAM, Disque, Températures CPU/GPU, Puissance électrique en W, Énergie cumulée en Wh, Runtime serveur et Uptime OS).
  - **Tiroir Latéral d'Historique (`TelemetryHistoryDrawer.tsx`)** :
    - Clic direct sur n'importe quelle carte métrique pour déployer un tiroir latéral animé depuis la droite avec courbe temporelle interactive (SVG responsive).
    - Filtres temporels rapides : **1 heure**, **6 heures**, **24 heures** et **7 jours**.
    - Affichage des extrêmes (minimum, maximum, moyenne) et horodatage dynamique.
- **Base de Données Dynamique & Évolutive (`SystemMetricLog`)** :
  - Table SQLite `system_metrics_logs` conçue selon un schéma extensible EAV (`metric_type`, `value`, `unit`, `recorded_at`), acceptant sans migration lourde toute nouvelle sonde matérielle future (watts, cpu, ram, disque, temp_cpu, temp_gpu, etc.).
  - Échantillonnage automatique et non bloquant orchestré par `scheduler_manager.py`.
- **Rétention Configurable & Purge Automatique (`logs_retention_days`)** :
  - Délai de conservation des journaux et des métriques matérielles paramétrable dans Paramètres (`GET`/`PUT /api/settings`, champ `logs_retention_days`, défaut : 7 jours).
  - Tâche de fond périodique (`_cleanup_old_logs_and_metrics`) purgeant atomiquement les enregistrements antérieurs au seuil configuré.
- **Collecte des Sessions (`playback_sessions`)** : traçage de chaque séance vidéo diffusée (id du cours, titre, canal, déclencheur manuel/planning, durée visionnée, durée totale, flag `completed` calculé à ≥90%).
- **Notation de Satisfaction (`course_ratings`)** : recueil des avis 1 à 5 étoiles après diffusion :
  - Affichage contextuel : sur le pupitre coach (`/grid`) dans le conteneur du cours terminé en mode double écran ; sur grand écran (`/cinema` HDMI) en mode headless.
  - Barre de décompte d'auto-fermeture (5 minutes / 300 s) continue et fluide, synchronisée sur l'horloge système.
  - Harmonisation chromatique intégrale : étoiles d'évaluation, jauges et icône d'alimentation (éclair et unité Watt) synchronisées sur la variable CSS du thème actif (`var(--accent-primary)`).
- **Tableau de Bord Analytique (`GET /api/metrics/dashboard`)** :
  - 4 indicateurs clés (Satisfaction moyenne /5, Taux de complétion %, Durée totale de diffusion en heures, Nombre de séances).
  - Histogramme d'affluence sur 24 heures (CSS Grid pur, détection automatique de l'heure de pointe).
  - Classement des cours les plus diffusés et les mieux notés.

---

## 4. Canaux de diffusion & Gestionnaire de lecture

Le système pilote deux canaux de diffusion vidéo **strictement indépendants**, plus un 3ᵉ canal musical (§5) :

1. **Canal Câblé (`channel=cable`)** : Canal d'affichage principal relié à la sortie vidéo physique du mini PC (écran salle / kiosque).
2. **Canal Réseau (`channel=network`)** : Canal secondaire destiné à la diffusion réseau ou aux écrans auxiliaires.
3. **Sorties radio (`radio_cable`, `radio_network`)** : musique continue, totalement indépendante des deux canaux vidéo. **Un moteur par sortie** (`radio_manager.py`, sur le modèle des gestionnaires câblé/réseau) : la radio câblée et la radio réseau ont chacune leur playlist, file d'attente, volume, rappels, planning et réglages de son. L'ancien identifiant `radio` reste accepté en entrée et désigne la sortie réseau. **La sortie câblée peut être basculée sur Radio à la demande** (cf. ci-dessous et §5) ; le réseau a déjà son poste radio par URL.

Chaque écran affiche `/kiosk` ou `/cinema` selon la sortie choisie par l'admin (`/api/settings/display-output`, ex. câble → `cinema`, réseau → `kiosk`). **La sortie câblée accepte aussi `radio`** (l'écran physique devient un poste radio, `/radio?channel=cable`) : la vidéo, le fond ou le cours audio en cours est arrêté, le moteur radio câblé reprend (ou démarre l'ambiance par défaut), et le retour vers kiosk/cinéma le met en pause sans perdre sa file. Le réseau refuse `radio`. `/kiosk` et `/cinema` du canal câblé suivent cette bascule (la requête `?channel=` est conservée), y compris au démarrage ; la page radio câblée ne repart que sur une bascule faite en direct. Tant que l'écran câblé est en mode Radio, les lancements vidéo sur le câblé sont refusés (`command_rejected`, raison `radio_locked`). L'écran câblé (`127.0.0.1`, détecté par `isWiredDisplay()`) suit toujours sa sortie stockée ; le canal d'un écran est explicite via `?channel=` (cf. « Identité de canal » ci-dessous). **Le pupitre studio `/grid` pilote exclusivement le canal câblé (HDMI)** : il n'y a pas d'interface `/grid` pour le canal réseau (qui se pilote depuis `/dashboard-network`). **Bibliothèque vide** : `/cinema` affiche un écran d'attente plein écran (grand logo + heure + « Aucun cours disponible ») au lieu d'un écran noir ; `/kiosk` a son propre écran d'attente (horloge + prochain cours). Les **catégories de cours** sont des libellés **libres** (plus de RPM/Sprint/The Trip figés) : saisie avec suggestions des catégories déjà utilisées, filtre et regroupement dynamiques.

**Contrôles universels : Télécommandes physiques, Claviers, Souris, Tactile et Manettes de jeu** (réf. hook `useKioskRemote` & HTML5 Gamepad API) : L'ensemble des interfaces de diffusion et de régie (`/cinema`, `/grid`, `/kiosk`, `/radio`) réagissent de manière cohérente à l'ensemble des périphériques d'entrée :
- **Télécommandes USB & Bluetooth** : dongles de présentation, télécommandes multimédias et "air remotes" reconnus en claviers HID standards.
- **Manettes de jeu (Gamepads)** : manettes Xbox, PlayStation (DualShock / DualSense), 8BitDo, Nintendo Switch Pro et manettes USB/BT génériques prises en charge nativement via la standard **HTML5 Gamepad API** (`navigator.getGamepads()`). D-Pad et stick analogique gauche pour la navigation, boutons A/Croix pour lancer/valider, B/Rond pour retour, X/Y/Start pour Play/Pause, L1/R1 pour saut temporel et L2/R2 pour le volume.
- **Tactile & Souris** : activation directe des cartes au clic/toucher, tap-to-wake des contrôles en lecture, bouton pause interactif et barre de défilement.
- **Navigation spatiale 2D (`moveDomFocus2D`)** : calcul géométrique continu dans le viewport pour déplacer le curseur de sélection de carte en carte (haut, bas, gauche, droite) avec halo lumineux dynamique (`.kiosk-remote-focus`).

### Reprise après interruption (Resilience Rule)

Lorsqu'une programmation automatique (`scheduler`) doit démarrer alors qu'une lecture manuelle est en cours :
1. Le `playback_manager` interrompt la lecture manuelle et sauvegarde la position exacte et l'identifiant du média dans `playback_state`.
2. Le cours programmé s'exécute.
3. À la fin de la programmation, l'interface propose automatiquement la **reprise à la seconde près** du cours interrompu.

### Récupération et fluidité de lecture (`/kiosk`, `/cinema`)

Sur certains décodeurs matériels (MediaCodec sur Android, VA-API sur Linux/Wyse), un seek vers une position hors keyframe à chaud pouvait laisser le pipeline vidéo désynchronisé ou bloqué sur la dernière image décodée alors que la piste audio continuait d'avancer. Plusieurs protections complémentaires et coordonnées couvrent ce cas dans `/kiosk` et `/cinema` :
1. **Seeks protégés et synchronisation pause/seeked** : toute assignation de `currentTime` passe par `seekWhenReady()`. Si l'élément est en cours de lecture, il est temporairement mis en pause pour figer l'horloge audio avant le saut temporel, puis relancé uniquement à la réception de l'événement `seeked` (avec timeout de secours à 1200 ms). Cela garantit que l'audio ne devance pas la reconstitution du GOP vidéo.
2. **Garde anti-réentrance** : interdiction de déclencher un nouveau seek tant que `el.seeking` est actif, évitant l'écrasement perpétuel du buffer décodeur.
3. **Période de grâce après seek (3 500 ms)** : sur les kiosques miroirs (réseau ou multi-écrans), les recalages périodiques de `position_tick` sont ignorés pendant 3,5 secondes après un seek pour laisser les tampons et l'affichage se stabiliser.
4. **Détection douce de décrochage sans saccade** : remplacement des watchdogs agressifs par une vérification non-destructive de gel prolongé (> 7,5s consécutives sans progression de l'horloge hors chargement/seek), déclenchant une relance propre `.play()` sans cycle artificiel de pause/seek saccadé.
5. **Protection anti-rebond (1,5s) et lissage temporel monotone sur `/grid`** : élimination des doubles commandes accidentelles au lancement de cours et affichage d'un temps de lecture régulier seconde par seconde sans saut arrière dû aux aléas de paquets réseau.

### Identité de canal et horloge de lecture serveur (4.0)

**Identité de canal explicite** (`frontend/src/lib/displayChannel.ts`, règle unique partagée par `/kiosk` et `/cinema`) : le paramètre d'URL `?channel=cable|network` est prioritaire ; sans lui, `/kiosk` reste câblé (décision historique : une TV sur IP LAN reste un écran câblé) et `/cinema` déduit son canal du nom d'hôte (`127.0.0.1` = câblé). La redirection kiosque ↔ cinéma **conserve** `?channel=` — avant la 4.0 elle le supprimait, ce qui reclassait « câblé » un écran réseau ouvert sur la machine du serveur. Un écran « Réseau » sur la machine du serveur s'ouvre donc via `/kiosk?channel=network` (lien dans le tableau de bord Réseau et dans Réglages). L'identifiant de kiosque est généré **par chargement de page** (plus de `localStorage` partagé entre onglets, qui rendait plusieurs onglets locaux « primaires »).

**Horloge de lecture pilotée par le serveur** (`backend/app/utils/playback_clock.py`, `PlaybackManager`) : la position d'un cours est une fonction du temps, `position(t) = position_ancre + (t − instant_ancre) × vitesse`, et non plus la dernière valeur rapportée par un kiosque. Chaque état diffusé porte l'ancre `clock = { pos, at_ms, rate, running }` ; `at_ms` peut être **dans le futur** (démarrage synchronisé : 400 ms au chargement, 150 ms pour play/seek) **uniquement s'il y a au moins deux écrans** de diffusion sur le canal ; avec un seul écran, aucun délai (réponse immédiate). L'ancre porte aussi une `epoch`, incrémentée à chaque ordre (démarrage, pause, seek, vitesse, arrêt). Conséquences : la position avance **sans aucun kiosque connecté** ; le tick de position passe de 4 Hz à un **heartbeat de 1 Hz** ; `report_position` ne sert plus qu'au suivi d'assiduité ; `video_ended` est **idempotent** (porte le `video_id` : tous les écrans l'envoient) et le serveur termine lui-même un cours dépassé de sa durée + 3 s.

**Suivi côté écran** (`lib/playbackClock.ts`, `lib/useVideoClockFollower.ts`) : l'écran estime son décalage avec l'horloge serveur par `time_sync` (aller-retour sur la WebSocket, médiane des échantillons au plus petit RTT), puis amène son `<video>` sur la position cible — **avant l'instant de départ** : en pause à la bonne position, `play()` à l'instant exact ; **en lecture** : dérive < 80 ms ignorée, au-delà `playbackRate` ajusté de ±5 % (**sans `seek`**, donc sans réinitialiser le décodeur matériel), un seul `seek` si la dérive dépasse 2 s (délai de grâce 1,5 s, 4 s minimum entre deux seeks). Un **ordre explicite** (changement d'`epoch` : télécommande, `/grid`, planning) est appliqué immédiatement — seek dès 0,3 s d'écart, sans délai de grâce ni anti-boucle : deux seeks +10 s enchaînés à la télécommande s'exécutent chacun aussitôt. Cible de précision : **< 100 ms** entre écrans du canal Réseau. Latences mesurées (navigateur et backend réels, en local) : chargement d'un cours ≈ 150 ms, pause 1 ms, play 2-4 ms, seek 6-8 ms.

**Diffusion filtrée par canal** : chaque client s'abonne (`subscribe`) ; le serveur n'envoie les évènements propres à un canal (`state_change`, `cinema_state`, `cinema_command`) qu'à ses abonnés. Les évènements globaux (`display_output`, `settings_change`, `display_mode_change`, `force_reload`, `update_progress`) ne sont jamais filtrés ; un client sans abonnement (ancien bundle en cache) reçoit tout.

### Projection HDMI plug-and-play (4.0)

Le **mode d'affichage câblé n'est plus une préférence figée** : chaque plateforme remonte le nombre d'écrans externes réellement connectés (`PUT /api/display/state`, idempotent, rejouable), le backend en déduit le mode effectif (`dual_screen` dès qu'un écran externe existe, sinon `headless`) et le diffuse (`display_mode_change`). Le réglage `display_mode_setting` vaut `auto` par défaut ; `dual_screen`/`headless` forcent le mode. Le rapport matériel est gardé **en mémoire** (fait instantané, jamais persisté) et ré-émis périodiquement.

| Profil | Détection | Action |
|---|---|---|
| **Android** | `DisplayListener` (ajout, retrait, **modification**), écrans privés exclus | `Presentation` → `/cinema/?channel=cable` ; token d'activité prioritaire (`MainActivity.activeActivity`) et repli `TYPE_APPLICATION_OVERLAY` (`SYSTEM_ALERT_WINDOW`) pour éliminer tout `BadTokenException` ; 15 essais rapides puis un essai / 5 s **sans abandon** ; état rapporté au démarrage, à chaque changement, puis toutes les 60 s |
| **Windows** | `EnumDisplayMonitors` (ctypes), sondage 2 s stabilisé | Fenêtre native `bobine-projector.exe` (WebView2) si disponible ; repli Edge/Chrome kiosque avec profil dédié, `--new-window`, `--window-position` et `--start-fullscreen` |
| **Linux Bureau** | `xrandr --listmonitors` (X11 / XWayland) | Fenêtre native `bobine-projector` (WebKitGTK) si disponible ; repli Chromium kiosque avec profil dédié, `--new-window`, `--start-fullscreen` et sous Wayland `--ozone-platform=x11` |
| **macOS** | `system_profiler SPDisplaysDataType` | Fenêtre native `bobine-projector` (`projector/`, WKWebView), écran externe choisi par la fenêtre elle-même ; repli navigateur par défaut si absente |
| **Appliance Wyse** | Règle udev DRM → `bobine-display-hotplug` (sysfs, anti-rebond 3 s) | `try-restart bobine-kiosk` uniquement si l'ensemble des sorties connectées change ; la logique `xrandr` de démarrage est réutilisée ; **ne rapporte aucun écran externe** (sa sortie EST l'affichage autonome) |

Implémentation desktop : `backend/app/desktop/displays.py` (énumération, `DisplayWatcher`, `ProjectorWindow`, `DisplayOrchestrator`, recherche multi-OS `find_native_projector`, testés sans affichage).
Sortie active : dans `backend/app/routers/settings.py`, la valeur par défaut du canal câblé est automatiquement dérivée vers `"cinema"` dès que le mode matériel effectif est `"dual_screen"`, empêchant la redirection intempestive de `/cinema` vers `/kiosk` lors du branchement d'un écran étendu.


### Double Décodeur Vidéo Gapless A/B Deck (`/cinema`) & Notation 5 Étoiles

- **Moteur Vidéo A/B Deck Gapless** : sur Chromium et WebView Android, l'assignation d'un nouveau `video.src` entraîne la destruction du pipeline de décodage matériel et génère un écran noir de 200 à 600 ms. Bobine monte désormais **deux éléments `<video>` permanents dans le DOM** (`deckARef` et `deckBRef`) au sein d'un conteneur `.cinema-deck-container`. Le Deck Actif joue en direct (`opacity: 1`, `zIndex: 2`), tandis que le cours suivant ou l'écran de veille est préchargé en coulisses sur le Deck en Attente (`opacity: 0`, `zIndex: 1`, `preload="auto"`). Dès confirmation de `canplay`, un fondu enchaîné matériel CSS (`opacity 0.4s ease`) s'opère sans le moindre clignotement ni flash noir.
- **Système de Notation 5 Étoiles** : à la fin naturelle d'un cours ou dès franchissement de 95% de progression, le widget de pilotage sur `/grid` (pupitre coach) ou l'écran cinématique de fin de cours sur `/cinema` (grand écran) propose une carte d'évaluation tactile et physique à 5 étoiles (Google Icons `star` / `star_outline`). Contrôlable à la télécommande multimédia, manette de jeu, souris ou tactile, avec décompte d'auto-fermeture de 5 minutes (300 s). Les avis sont persistés en base SQLite (`course_ratings`).
- **Sessions de Lecture & Assiduité** : chaque diffusion vidéo est tracée dans la table `playback_sessions` avec le canal, le type de déclencheur, la durée exacte visionnée et le flag `completed` (vrai si ≥ 90% du cours a été suivi), alimentant le tableau de bord `/metrics`.

### Studio Modal de Cours Zéro-Scroll (`/library`) & Sous-titres Synchronisés

- **Studio Modal Zéro-Scroll** : L'édition d'un cours vidéo dans la bibliothèque (`/library`) se fait dans un canevas Studio 2 colonnes sans défilement vertical (`.course-studio-modal`). La colonne gauche intègre un lecteur 16:9 interactif avec prévisualisation des sous-titres, sélecteur de miniature, specs techniques en grille Bento (résolution, codec, fps, débit, chemins disques) et actions système (normalisation manuelle, suppression). La colonne droite regroupe le titre, les métadonnées de programme et release, le synopsis multi-lignes étendu et le gestionnaire de sous-titres synchronisés.
- **Pipeline et Gestionnaire de Sous-titres (`app/utils/subtitles.py`)** : Prise en charge native des fichiers `.srt` et `.vtt`. Détection automatique de la langue d'après le nom de fichier (`cours.fr.srt` $\to$ Français), conversion automatique SRT en WebVTT standardisé (normalisation des horodatages virgule/point, UTF-8, en-tête `WEBVTT`) et exposition via `GET /api/videos/{id}/subtitles/{sub_id}/vtt` avec en-têtes CORS (`Access-Control-Allow-Origin: *`).
- **Diffusion Synchronisée Sous-titres Cinéma & Kiosque** : Rendu des sous-titres via éléments `<track kind="subtitles">` sur les décodeurs Deck A et Deck B. Sélecteur interactif type Netflix dans la régie cinéma (`.cinema-subtitle-popover`) et styles typographiques haute lisibilité (`video::cue` avec arrière-plan sombre translucide et bordures adoucies).
- **Sous-titres : URL de piste et choix depuis l'administration** : l'API renvoie `vtt_url` déjà préfixé par `/api` ; `frontend/src/lib/subtitles.ts` (`subtitleSrc`) retire ce préfixe avant `getApiUrl`, faute de quoi la piste visait `/api/api/...` et restait vide (`readyState 3`). Le mode de chaque `<track>` est forcé (`applySubtitleMode`) car l'attribut `default` n'est pas fiable sur un `<video>` réutilisé d'un cours à l'autre. La commande WebSocket `set_subtitle` (`{track_id | "off"}`) mémorise le choix dans l'état de lecture (`subtitle`), diffusé aux écrans ; le tableau de bord et la télécommande mobile s'en servent pour sélectionner la piste affichée sur `/kiosk` et `/cinema`.
- **Chapitres de cours (`app/utils/chapters.py`, `routers/chapters.py`)** : table `video_chapters` (début, fin, titre, 200 chapitres maximum, titres de 120 caractères). `GET/PUT /api/videos/{id}/chapters` lisent et remplacent la liste ; `POST .../chapters/import` accepte JSON (`{"chapters": [{"start", "end"?, "title"}]}` ou liste nue, titre éventuellement localisé), WebVTT de type chapitres ou texte « 05:00 Titre » (format reconnu d'après le contenu) ; `POST .../chapters/from-file` extrait les chapitres incorporés au fichier avec FFprobe ; `GET .../chapters/export` rend le JSON d'import. Une erreur de lecture est renvoyée avec la ligne en cause et ne modifie rien. Côté interface : `ChapterEditor` (bibliothèque), `ChapterTicks` (repères sur la progression), `ChapterList` (saut), `ChapterToast` (bandeau au changement de chapitre sur `/kiosk` et `/cinema`).
- **Adresse réseau présentée (`app/utils/network.py`)** : `primary_lan_ip()` énumère les interfaces actives, écarte les interfaces virtuelles (VPN, conteneurs, machines virtuelles, réseau mobile) et préfère une adresse privée de Wi-Fi puis d'Ethernet ; l'ancienne méthode (socket UDP vers 8.8.8.8) renvoyait l'interface de la route par défaut, donc l'adresse du VPN. Sur Android, la couche native lit l'adresse Wi-Fi/Ethernet via `ConnectivityManager` et la transmet par la variable d'environnement `BOBINE_LAN_IP`. `GET /api/settings` expose `network.local_ip` et `network.local_ips` ; l'annonce mDNS utilise le même choix.
- **Android : démarrage avec l'appareil et mises à jour** : `BootReceiver` (`BOOT_COMPLETED`, `QUICKBOOT_POWERON`, `MY_PACKAGE_REPLACED`) relance le service de premier plan quand l'option Réglages → « Démarrage de l'appareil » est active (pont JavaScript `BobineNative`). Le lancement de l'écran depuis l'arrière-plan reste soumis aux restrictions d'Android (autorisation « Afficher par-dessus d'autres applications », réinitialisée à chaque redémarrage sur certains boîtiers Android TV). Le build Google Play (type `play`, `BuildConfig.STORE_BUILD`) retire `REQUEST_INSTALL_PACKAGES` et désactive la mise à jour intégrée (`ProfileHandler.is_store_managed()`, `/api/updates/check` renvoie `store_managed`). `UpdateManager` vérifie `canRequestPackageInstalls()` avant de télécharger et ouvre le réglage « sources inconnues » au besoin. Le splash et la barre d'état reprennent les couleurs du thème choisi, et le splash affiche le logo du canal de mise à jour (Stable, Bêta, Canary) : l'interface les pousse au pont natif (`setThemeColors`, `setUpdateChannel`, valeur venue du serveur uniquement) et le démarrage les relit de façon synchrone, sans attendre le backend embarqué (`SplashChannel`, partagé par l'écran tactile et la sortie HDMI ; l'interrogation de `/api/settings` ne sert plus que pour le tout premier lancement).
- **Interface téléphone** : `responsive.css` regroupe les règles mobiles (studio en feuille plein écran, tableaux en cartes, onglets de réglages). `Sheet` et `ResponsiveSelect` remplacent les listes déroulantes par des feuilles avec recherche sur écran étroit (sélecteur natif sur ordinateur) ; `MobileRemote` porte le widget « En cours » et la feuille « Lancer un cours » (onglets Cours / Playlists / Fonds, aperçu avec miniature et durée).
- **Menu de Pause Netflix** : Lors de la mise en pause sur grand écran (`/cinema`), l'interface déploie un panneau cinématique 2 colonnes paysage : vignette du cours avec bouton de reprise et horloge sur la gauche, métadonnées complètes, badges de qualité et synopsis intégral défilant avec fluidité sur la droite.
- **Écran de démarrage statique Android** : Pour éliminer tout flash d'erreur HTTP transitoire (1 à 2 secondes) au lancement de l'application Android ou lors de l'initialisation de la sortie secondaire HDMI (`BobinePresentation`), un splash screen natif avec logo Bobine et indicateur de chargement masque la vue web jusqu'à ce que le backend FastAPI embarqué réponde avec succès (`onPageFinished`), assurant une transition visuelle fluide et élégante.

---

## 5. Module Radio

Sous-système musical « type Spotify » **totalement indépendant** des cours vidéo/audio coach (canal `radio` dédié, tables `radio_*`, gestionnaire d'état `radio_manager.py`) — bibliothèque, playlists, lecture continue, crossfade et rappels sonores.

- **Deux sorties radio indépendantes (5.0.1)** : `/radio?channel=cable` (sortie câblée, jouée par l'écran physique quand il est basculé sur Radio) et `/radio?channel=network` (sortie réseau, n'importe quel appareil) ; `/radio` nu reste un alias de la sortie réseau (règle unique dans `lib/displayChannel.ts`, sans heuristique de nom d'hôte). Chaque sortie a son propre moteur, son rôle primaire WebSocket et ses évènements (`channel` = `radio_cable` ou `radio_network`). La bibliothèque musicale, les playlists et le pool de rappels restent **uniques** ; sont propres à chaque sortie : l'état de lecture, l'ambiance par défaut (réglage `radio_default_playlist_id_<sortie>`, sinon la playlist `is_default`, sinon toute la bibliothèque), le démarrage auto (le moteur câblé ne démarre que si l'écran câblé est sur Radio), les règles de rappel (colonne `target` : `radio_cable`, `radio_network` ou `both`) et le planning (quatre voies : câblé, réseau, radio câblée, radio réseau ; les anciennes lignes `radio` migrent vers `radio_network`). Une programmation de la radio câblée alors que l'écran n'est pas sur Radio charge sa playlist en pause, sans basculer l'écran. La télécommande (`RadioRemotePanel`) est un composant unique monté dans `/radio-remote` (onglets Câblée / Réseau), dans la page « Sortie Câblé » en mode Radio et dans `/grid` (variante compacte). Le lecteur s'arme tout seul quand le navigateur autorise la lecture automatique (sonde `AudioContext`, détection de fonctionnalité) : indispensable sur les sorties câblées où personne ne peut cliquer.
- **Gestion du son (5.0.1)** : égaliseur graphique 5 bandes (60 Hz, 230 Hz, 910 Hz, 3,6 kHz, 14 kHz, ±12 dB), renfort des basses (0 à +12 dB), loudness, protection anti-saturation (limiteur, actif seulement quand les réglages relèvent le son) et trois préréglages (Bass Boost, Voix Boost, Adoucis ; le son à plat est le bouton Réinitialiser, pas un préréglage). Le traitement est fait **dans le lecteur** (`lib/radioSoundGraph.ts` : une seule chaîne Web Audio de 9 nœuds pour toute la musique, préampli automatique anti-écrêtage, changements lissés) ; les rappels vocaux la contournent. Le serveur (`utils/radio_sound.py`) borne sans erreur, persiste par sortie (`radio_sound_<sortie>` dans `settings`) et diffuse les réglages dans l'état du moteur (champ `sound`, commande WebSocket `radio_set_sound`, `GET/PUT /api/radio/sound?channel=`). Interface : `RadioSoundPanel` (dans la télécommande radio, donc aussi la page Sortie Câblé en mode radio et `/grid`).
- **File « À suivre » (5.0.1)** : `RadioQueueList` affiche pochette, titre, artiste, style (`genre`, transmis dans l'état de chaque piste) et durée, avec glisser-déposer par évènements « pointer » (souris, toucher, stylet) et flèches au clavier. La commande WebSocket `radio_move_in_queue` (`from_index`, `to_index`) réordonne les seules pistes à venir (`RadioPlaybackManager.move_in_order` : la piste courante et l'historique ne bougent jamais). Les listes déroulantes (`ResponsiveSelect`) sont riches (aperçu, détail, durée, recherche intégrée) et tous les champs de recherche passent par `lib/searchText.ts` (casse et accents ignorés, mots dans n'importe quel ordre) avec autocomplétion (`SearchBox`).
- **Surfaces** : `/radio` (écran du poste dédié — affichage + contrôles, ouvert à la main dans un navigateur, pas de service kiosk systemd), onglet admin « Radio » (télécommande à distance sur `/radio-remote`), « Piste Audio Radio » (bibliothèque sur `/radio-library`), « Rappels » (annonces sur `/radio-announcements`), et un 3ᵉ onglet « Radio » sur la page Planning (`/schedule/?channel=radio`). Hors diffusion (écran d'attente + overlay « Démarrer la radio »), le poste affiche un **grand logo plein écran** (fond opaque du thème) ; déverrouiller le poste **ne lance aucune musique** tant qu'aucune radio n'est réellement active (état `idle`), pour ne pas désynchroniser l'interface admin.
- **Bibliothèque** : import tous formats audio (transcodage automatique de ce que le navigateur ne lit pas), pochettes extraites (ID3) ou manuelles, navigation par artiste/album/tags. L'écran admin « Piste Audio Radio » (`/radio-library`) est une **vue d'ensemble** : barre latérale de filtres (playlists / tags / genres / artistes), grille à sélection multiple avec actions groupées (taguer, ajouter à une playlist), tags éditables en chips, éditeur de playlist en glisser-déposer.
- **Lecture** : continue, file d'attente, lecture aléatoire, répétition (piste/playlist), **crossfade** (Web Audio API — deux `<audio>` routés dans un graphe `MediaElementAudioSourceNode → GainNode → destination`, fondu démarré côté client en avance sur la confirmation serveur).
- **Rappels** : annonces de bienséance avec description, règles de déclenchement (toutes les N musiques / toutes les X minutes / à heures fixes / manuel), insertion en attente de fin de piste ou par fondu immédiat (« duck » — réutilise le même graphe Web Audio que le crossfade). Chaque rappel est **normalisé en loudness à l'import** (`ffmpeg loudnorm` EBU R128, 2 passes, cible -10 LUFS) pour s'entendre au moins aussi fort que la musique. Écran d'admin dédié (`/radio-announcements`) : import, activation, règles, déclenchement manuel.
- **24/7 & Planning** : une playlist marquée par défaut (`is_default`) tourne en boucle en permanence ; auto-démarrage au boot (`radio_autostart_on_boot`). **Sans aucune playlist par défaut, le repli joue toute la bibliothèque en aléatoire et en boucle** (playlist virtuelle « Toute la bibliothèque », `playlist_id=None`, recomposée à chaque lancement donc toujours à jour avec la bibliothèque) : la radio n'est jamais muette au démarrage sans qu'il faille créer une playlist ; définir une `is_default` reprend la priorité. Le Planning peut y superposer des fenêtres horaires récurrentes (option 24/7) qui, en fin de fenêtre, reviennent à l'ambiance par défaut — ou, à défaut, à ce même repli bibliothèque plutôt qu'au silence.
- **Config** (`radio_dir`, `radio_covers_dir`, `radio_announcements_dir`, `radio_watch_dir`, `radio_volume_default`, `radio_crossfade_seconds`, `radio_announcement_duck_level`, `radio_announcement_fade_ms`, `radio_autostart_on_boot`) : voir `config.py` — dossiers unifiés sous `${REPO_DIR}/data` par `install.sh` comme le reste des médias.

---

## 5bis. Périphériques (audio, Bluetooth, Wi-Fi)

Onglet `/devices` (5.0.2) : gestion des périphériques de la machine qui diffuse, **désactivée par défaut**.

- **Interface de pilote** (`backend/app/devices/base.py`, `DeviceDriver`) : audio, Bluetooth, Wi-Fi et réglages du système derrière des **capacités déclarées** (`audio_list`, `bluetooth_pair`, `wifi_connect`…). L'interface n'affiche que ce que l'OS permet ; aucune erreur d'OS ne devient une 500 (`DeviceError` : code stable + message, ou `{"supported": false, "reason"}`).
- **Pilotes** (`registry.py` choisit selon le profil de déploiement) : `linux.py` (PipeWire par `pw-dump`/`wpctl`, BlueZ par D-Bus avec `dbus-fast` et un agent d'appairage, NetworkManager par `nmcli` — mots de passe sur l'entrée standard, jamais en argument) ; `sidecar.py` + crate Rust `devices/` (`bobine-devices`, Windows et macOS : JSON-RPC 2.0 sur stdin/stdout, versionné, liste blanche de méthodes, paramètres validés, aucun port, lancé à la demande, relancé après panne) ; `android.py` + `DeviceBridge.kt` (sorties audio, Bluetooth, Wi-Fi en lecture seule sans SSID, liens vers les réglages d'Android). Les analyseurs de sorties d'outils sont purs et testés (`linux_parse.py`, `devices/src/parse.rs`).
- **Garde-fou « validé sur matériel »** : Linux est validé en lecture sur matériel réel ; Windows et macOS restent bloqués (« non pris en charge ») tant que `BOBINE_DEVICES_EXPERIMENTAL=1` n'est pas défini.
- **Sécurité** (`security.py`) : écran local de confiance (127.0.0.1/::1 ou une adresse de la machine) ; tout autre appareil saisit un **PIN à 6 chiffres** (scrypt + sel, `settings.devices_pin_hash`, jamais renvoyé par l'API ni journalisé, exclu des sauvegardes), échangé contre un cookie `HttpOnly; SameSite=Strict` signé en HMAC, lié à l'IP, glissant (15 min). 5 essais par IP puis blocage de 1 à 15 min. Le PIN ne se définit et la fonction ne s'active que depuis l'écran local ; réinitialisation sans ancien PIN depuis l'écran local ou `install.sh --reset-devices-pin`.
- **Détail d'une sortie audio** (5.0.2) : un clic ouvre un tiroir (`AudioDetailSheet`) — niveau, **balance** gauche/droite (PipeWire : `pw-cli set-param … Props channelVolumes`, volumes cubiques, niveau maître conservé), **son de test** par canal (WAV généré en mémoire, `pw-play --target`, plafonné, un seul à la fois), **analyse** (`pw-dump` : état, canaux, fréquence, format, latence, carte, codec Bluetooth), **profil** (`wpctl set-profile`), nom personnalisé et masquage (`settings.devices_audio_meta`, communs à toutes les plateformes). Capacités `audio_details`, `audio_balance`, `audio_test_tone`, `audio_profile` ; routes `GET /audio/details`, `POST /audio/balance|test|profile`, `PUT /audio/meta`. Android : analyse de base seulement.
- **Vue globale** (5.0.2) : `GET /api/devices/topology` assemble un graphe (`devices/topology.py`, pur et testé) — machine au centre, sorties audio, appareils Bluetooth, Wi-Fi, Ethernet (psutil, hors interfaces virtuelles), écrans et télécommandes Bobine. Le moyen de liaison d'un client est déduit de son adresse (machine elle-même, sous-réseau du Wi-Fi, de l'Ethernet, sinon réseau local). Côté serveur, `identify` accepte `page` pour les kiosks et un rôle `viewer` (cinéma, grille, tableau de bord, coach) enregistré dans un registre séparé de `ws_manager` (`client_snapshot`) **sans effet** sur le rôle primaire ni sur les évènements. Côté interface : disposition orbitale déterministe (`lib/deviceMap.ts`, aucune simulation), SVG avec déplacement, zoom (molette, pincement), survol et panneau de détail avec raccourci vers l'onglet de l'appareil (`focus`).
- **PIN et interactions** (5.0.2) : saisie en six bulles (`PinEntry`, logique pure `lib/pinEntry.ts`), définition en deux temps ; jetons de mouvement `--ease-*`, classe `.glass-interactive` (halo piloté par `usePointerGlow`, souris précise seulement, désactivé en mode télécommande et mouvement réduit), onglets `SegmentedTabs` à indicateur glissant. Les barres d'outils passent à la ligne selon leur contenu (`scripts/browser-bench/overflow_audit.py` en garde-fou). Android : spinner `ArcSpinnerView` aux couleurs du thème (`BobineNative.setThemeAccent`).
- **Wi-Fi** : le mot de passe d'un nouveau réseau n'est accepté que depuis l'écran local ; toute connexion ou coupure arme un **retour automatique à l'ancien réseau sous 60 s** sauf confirmation (`POST /api/devices/wifi/confirm`) ; un appareil joint par ce même Wi-Fi doit d'abord acquitter l'avertissement (`acknowledge_disconnect`).
- **Temps réel** : l'évènement WebSocket `devices_changed` (`{scope: audio|bluetooth|wifi}`) ne porte **aucune donnée** ; les clients relisent l'état par REST, derrière le PIN. Une boucle de surveillance (8 s, seulement si un client écoute) détecte les changements extérieurs.
- **Android** : permissions limitées à `BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN` (`neverForLocation`) et `ACCESS_WIFI_STATE`, aucune localisation ; la demande « Appareils à proximité » n'est affichée que sur action explicite de l'utilisateur.
- **Google Play** (build `play`) : *Réglages → Mises à jour* passe par l'API In-App Updates (`PlayUpdateProvider`, chargée par réflexion depuis `StoreUpdates` : la version libre ne contient aucune bibliothèque Google) ; routes `POST /api/updates/store/{start,complete,open}` ; `GET /api/settings` expose `store_managed`.

---

## 6. Mode Audio Coach & Hub d'Ambiances Visuelles

Le mode **Audio Coach** permet de diffuser des cours audio (pistes vocales / musique rythmée) sur l'équipement sonore de la salle tout en projetant une ambiance visuelle dynamique et cinématique sur l'écran câblé (HDMI).

- **Console Régie Coach (`/coach`)** : Console de pilotage studio réactive et tactile.
  - **Sur tablette paysage et ordinateur (>= 900px)** : Disposition double colonne asymétrique ergonomique.
    - *Colonne gauche* : Informations de piste, barre de progression interactive, minuteur de repos/exercice, contrôles de transport tactiles surdimensionnés, curseur de volume réactif, boutons de bouclage/enchaînement, et playlist intégrée déroulante avec saut direct de piste.
    - *Colonne droite* : **Stage Monitor 16:9** (retour vidéo en direct du flux HDMI de salle avec vidéo, pochette ou halo cinématique sobre, et incrustation en direct du titre et de la progression) surmontant une **Palette tactile d'ambiances 16:9** permettant de commuter l'ambiance visuelle projetée en direct en 1 touche sans rupture sonore.
  - **Sur smartphone et écran compact (< 900px)** : Interface monoposte épurée avec tiroirs tactiles rétractables (*bottom sheets*) pour la sélection rapide des pistes et des ambiances visuelles.
- **Redirection automatique vers la régie** : Dès que le mode Coach est activé sur la borne, toute ouverture ou navigation vers le tableau de bord câblé (`/dashboard-cable`) redirige automatiquement et instantanément vers `/coach`, assurant une coordination sans friction pour tout le personnel ou le coach intervenant depuis un terminal mobile ou un poste déporté.
- **Hub d'Ambiances Visuelles (`/backgrounds`)** : Espace centralisé dédié à la gestion des boucles d'ambiance visuelle 16:9. Fini l'ancien commutateur non intuitif : chaque carte propose une prévisualisation vidéo en survol dynamique, des badges de diffusion en direct (« Sur Câblé », « Sur Réseau », « Par défaut Coach »), un lecteur modal immersif complet, des boutons de diffusion immédiate 1-clic hors séance, et la possibilité d'assigner l'ambiance par défaut (`default_coach_background_id`).
- **Sélecteur Visuel Audio (`/audio`)** : L'assignation d'ambiance dans la bibliothèque audio s'effectue via une carte 16:9 interactive ouvrant une galerie visuelle de sélection avec miniatures, remplaçant l'ancien menu textuel.
- **Minuteur d'enchaînement (`audio_chain_timer_seconds`)** : Délai de transition configurable entre deux pistes audio (modifiable depuis `/api/settings`).
- **Persistance et Repli** : Persistance du réglage `default_coach_background_id` dans la table SQLite `settings`. Tout cours audio sans fond spécifique attribué hérite automatiquement de l'ambiance par défaut configurée.

---

## 7. Script d'installation & Services systemd

L'installation de production s'effectue via le script shell idempotent `install.sh` sur Debian 13 (Trixie).

```bash
# Installation complète sur la machine cible
sudo ./install.sh

# Ou en une commande, sans dépôt local (le script récupère le code lui-même)
curl -fsSL https://bobine.fit/install.sh | bash
```

Lancé hors d'une copie de Bobine (tube `curl | bash`, ou fichier copié seul), `install.sh` **s'amorce** (`bootstrap_standalone`) : il demande `sudo` de lui-même (sans `sudo -E`, qui exige un droit `SETENV`), installe `git`/`curl` si le système est minimal, clone le dépôt (clone allégé `--filter=blob:none`) dans `~<compte>/Bobine` à la dernière Stable — ou au tag mobile du canal choisi (`beta`/`canary`) avec `--channel=beta|canary` —, puis se relance depuis ce dépôt. Les questions de langue et de canal se posent sur `/dev/tty` même quand le script arrive par un tube, et sont sautées sans terminal (CI, SSH sans PTY). Avant toute modification, `preflight_network` corrige une horloge dérivée (pile CMOS à plat : sans cela les certificats TLS sont « pas encore valides » et apt échoue) et vérifie l'accès à GitHub avec un message précis. Les appels apt attendent le verrou `unattended-upgrades` (`DPkg::Lock::Timeout`) et réessaient (`Acquire::Retries`). Les étapes longues affichent un indicateur animé (dernière ligne utile du journal + temps écoulé) sur un vrai terminal ; l'écran final donne l'IP du réseau local et un code QR (`qrencode`) pour ouvrir l'administration depuis un téléphone. Si le checkout du canal remplace `install.sh` par une autre version, il se relance une fois depuis la nouvelle (garde `BOBINE_REEXEC`). Le CI exécute l'amorçage en `--dry-run` via un tube (régression historique : `${BASH_SOURCE[0]}` non défini sous `set -u` faisait planter la commande annoncée dans le README avant tout message).

### Options d'installation (`sudo ./install.sh --help`)

| Option | Description |
|---|---|
| `--no-kiosk` | Installation du backend seul (sans Chromium X11 / audio) |
| `--dry-run` | Prévisualisation des actions sans modification |
| `--check` | Diagnostic de l'installation existante |
| `--skip-packages` | Mise à jour du projet (après déploiement du code, §9) sans réinstaller les paquets `apt` |
| `--skip-build` | Ne reconstruit pas le frontend Next.js |
| `--as-user LOGIN` | Compte cible quand le script tourne en **root direct** (Debian **sans sudo**, lancé via `su -`) — cf. ci-dessous |
| `--channel=stable\|beta\|canary` | Canal de mise à jour (défaut `stable`) — cf. « Canal de mise à jour » ci-dessous |
| `--progress=json` | Sortie **machine** : une ligne JSON par évènement (`run_begin` / `step` `start\|ok\|skip\|error` / `run_end`) sur le **fd 3**, pour piloter une barre de progression (assistant graphique). Le journal humain reste inchangé — cf. « Assistant d'installation » ci-dessous |
| `--uninstall [--purge] [--purge-data]` | Désinstallation progressive du système |

**Détection matérielle dynamique** : l'installateur ne suppose plus un GPU Intel. Il détecte le GPU (`lspci`) et le CPU (`lscpu`) et installe les paquets adaptés — **Intel** : `intel-media-va-driver-non-free` (repli `i965-va-driver`) ; **AMD/Ryzen** : `mesa-va-drivers` + `firmware-amd-graphics` ; **NVIDIA** : décodage logiciel + avertissement — plus le **microcode** (`amd64-microcode`/`intel-microcode`) et le firmware Wi-Fi si une interface sans fil est présente. Les paquets non libres exigeant des composants APT absents (`non-free`, `non-free-firmware`, séparés depuis Debian 12) sont gérés en **activant ces composants** au besoin (sauvegarde `.bobine.bak` des sources).

**Audio** : `alsa-utils` (`amixer`/`aplay`/`alsactl`) et la pile `pipewire`/`pipewire-pulse`/`wireplumber`/`pulseaudio-utils` sont installés systématiquement — sans eux, la configuration WirePlumber écrite plus bas (commutation automatique de prise jack, anti-sifflement) et les commandes `amixer`/`pactl` de `kiosk-xinitrc`/`bobine-audio-mute.sh` échouaient silencieusement sur un Debian minimal (netinst). Une étape **`capabilities`**, en fin d'installation (et rejouable via `--check`), vérifie que l'audio (`aplay -l`) et le décodage matériel VA-API (`vainfo`, profil H.264) fonctionnent réellement plutôt que de supposer que la configuration a suffi.

**Optimisations système** (étape `tuning`) : gouverneur CPU réglé sur `performance` (`bobine-cpu-governor.service`, machine branchée secteur en continu) et journal systemd plafonné à 200 Mo (`/etc/systemd/journald.conf.d/bobine.conf`) — la mise en veille d'écran (DPMS/screensaver X11) est déjà désactivée dans `kiosk-xinitrc` depuis une version antérieure.

**Privilèges — deux chemins** : soit `sudo ./install.sh` depuis un compte normal (le script refuse d'être root sans compte cible) ; soit, sur un Debian minimal **sans sudo** (mot de passe root défini à l'install, utilisateur non-sudoer), en **root direct** via `su - -c "\$PWD/install.sh --as-user <login> -y"`. Le script installe alors `sudo` et pose la règle sudoers restreinte, de sorte que les boutons « Synchronisation » / « Désinstaller » de l'admin fonctionnent ensuite. Les commandes exécutées « en tant que l'utilisateur » (venv, pip, build) passent par `sudo -u` si présent, sinon `runuser`.

### Services Systemd créés

- `bobine-backend.service` : API FastAPI Uvicorn sur le port 8000 (mono-processus, `--workers 1`). `Restart=always`.
- `bobine-kiosk.service` : Mode Kiosque Chromium plein écran sur `xinit` (X11). `Restart=always`.
- `bobine-audio-guard.service` : garde AUDIO uniquement — oneshot qui coupe Master/Speaker/Headphone au boot et à l'arrêt (silence hors session kiosque), recouverts par `kiosk-xinitrc` une fois prêt. Ne surveille rien d'autre.
- `bobine-watchdog.timer` + `bobine-watchdog.service` : chien de garde de SANTÉ. Le timer déclenche `scripts/watchdog.sh` (`OnBootSec=90s`, puis toutes les 30 s) qui consomme `GET /api/health` et **redémarre automatiquement un composant mort** : si `/api/health` ne répond pas 200 → relance de `bobine-backend` ; si le service kiosk est activé mais qu'aucun processus Chromium n'est présent → relance de `bobine-kiosk`. Complète `Restart=always` (mort du *processus*) pour les défaillances *logiques* (backend vivant mais base verrouillée, Chromium gelé…).
- `bobine-redirect.service` : Redirection nftables du port 80 vers 8000.
- `bobine-cpu-governor.service` : oneshot qui règle le gouverneur CPU sur `performance` à chaque démarrage (étape `tuning` de l'installateur).

**Contrôle de santé** — `GET /api/health` renvoie `{"status": "ok"|"degraded", "components": {"database", "kiosk"}}`, avec HTTP `200` si la base répond, sinon `503` (l'état du kiosque est indicatif et n'affecte pas le code HTTP). C'est le point consommé par le watchdog ci-dessus et par toute supervision externe.

Pas de service dédié pour le canal Radio (cf. §5) : `/radio` s'ouvre à la main dans un navigateur, sur le même backend.

### Assistant d'installation graphique

Une application graphique autonome (`assistant/`, développée avec **Tauri 2 / Rust**) tourne sur le **poste de l'administrateur** (Windows, macOS ou Linux), localise le mini PC sur le LAN (balayage de chaque interface réseau locale avec son vrai masque, de /24 à /22, résultats en direct, table ARP et nom `bobine.local` en renfort), s'y connecte en SSH, audite le matériel, puis **déroule `install.sh`** avec une barre de progression et un suivi temps réel des journaux d'installation. `install.sh` reste la **source de vérité unique** — l'assistant l'**orchestre**, il ne réimplémente rien. Détails complets et instructions de compilation : [`assistant/README.md`](../assistant/README.md).

Le scan réseau affiche **tous** les appareils qui répondent (pas seulement les cibles Bobine) — nom d'hôte, IP, indice d'OS, ports ouverts — pour qu'un utilisateur préparant un déploiement headless reconnaisse sa borne au milieu du reste du réseau. `install.sh` est embarqué dans l'assistant à la compilation et téléversé sur la cible (`bash /tmp/…`) : aucun dépôt, `git` ni `curl` préalable n'est nécessaire sur la borne, et l'hôte peut être saisi par nom (`bobine.local`). Le code de sortie réel du script est vérifié et un échec est affiché avec « Réessayer » et « Copier le journal ». L'authentification SSH accepte, en plus du mot de passe, une clé privée importée explicitement via un sélecteur de fichier natif (`tauri-plugin-dialog`).

### Canal de mise à jour (Stable / Bêta / Canary)

Trois canaux, choisis à l'installation (`install.sh --channel=stable|beta|canary`, ou dans le wizard de l'assistant Tauri) puis modifiables à tout moment depuis Réglages → Mises à jour (sélecteur « Canal de mise à jour ») :

- **Stable** (défaut) : `GET /api/updates/check` interroge `/repos/.../releases/latest` — exclut structurellement les pre-releases côté API GitHub, donc ce canal ne peut jamais en recevoir une, même en cas de bug applicatif. Chaque version stable a son propre tag `Vx.y.z` et sa propre entrée sur GitHub Releases (historique normal).
- **Canary** : interroge `/repos/.../releases/tags/canary` — un tag **unique et mobile**, republié en place à **chaque push sur `main`**, zéro curation (dernier commit, non testé). C'est l'ancien canal `beta` (rolling), renommé le 2026-10-16.
- **Bêta** : interroge `/repos/.../releases/tags/beta` — même mécanique de tag unique et mobile, mais republié **uniquement sur déclenchement manuel** du mainteneur (jamais sur un simple push) : un lot de fonctionnalités/correctifs choisi, plus testé que Canary.

Pour Bêta comme pour Canary, la détection de mise à jour compare le **commit** installé au commit visé par le tag du canal (`target_commitish`) — il n'y a pas de numéro de version qui avance à chaque build sur ces deux canaux. Une version stable équivalente ou plus récente remplace toujours la bêta/canary suivie.

Le choix est persisté (réglage `update_channel` en base pour le backend ; `/etc/bobine/update-channel` pour `install.sh`, non relu par le backend — deux sources de vérité indépendantes) et pilote aussi `apply_update()` du profil headless (bouton « Mettre à jour ») : `git checkout <tag>` plutôt qu'un `git pull --ff-only`, ce qui permet un vrai retour arrière (downgrade) vers un tag antérieur — et suit correctement un tag mobile (`git fetch --tags --force`).

Côté publication (`.github/workflows/ci.yml`) : le job `version` calcule à la fois le numéro de version (source de vérité unique : le fichier `VERSION` à la racine du dépôt) et le **canal**, structurellement séparés à partir de là :
- un tag `Vx.y.z` strict poussé → `release-stable` (nouvelle entrée GitHub Releases, `prerelease: false`, notes tirées de `docs/releases/<TAG>.md`, qui doit exister) ;
- un push direct sur `main` (hors tag), ou un déclenchement manuel (`workflow_dispatch`, case *publish_canary* cochée, depuis n'importe quelle référence — utile pour republier sans nouveau commit) → `release-canary` (force-déplace le tag `canary` sur le commit courant, supprime puis republie l'unique release Canary, notes générées automatiquement — changelog depuis le dernier tag stable). La Canary suit donc `main` en continu, sans jamais prendre de retard ;
- un déclenchement manuel UNIQUEMENT (`workflow_dispatch`, case *publish_beta* cochée) → `release-beta`, même mécanique que `release-canary` sur le tag `beta`, jamais sur un simple push.

Les noms de fichiers des artefacts Bêta/Canary sont **fixes** (`Bobine-Setup-beta.exe`/`Bobine-Setup-canary.exe`, `Bobine-beta.dmg`/`Bobine-canary.dmg`, `bobine_beta_amd64.deb`/`bobine_canary_amd64.deb`) — jamais de version ni de caractère `~` dedans (GitHub Releases réécrit silencieusement `~` en `.` dans les noms d'assets téléchargés). Le numéro de version *interne* (affiché dans l'app, champ `Version:` du paquet Debian) reste précis : `VERSION`/`COMMIT` sont bundlés dans chaque paquet (mêmes `datas` PyInstaller que `config.toml`) et lus au runtime par `app.utils.version` — y compris sur les profils packagés (Windows/macOS/Linux desktop), qui n'ont pas de `.git` pour se renseigner autrement.

#### Robustesse du pipeline de mise à jour

- **Retour en Stable** : quand le build local est une Bêta/Canary (version `x.y.z-beta`/`x.y.z-canary`, ou checkout headless posé exactement sur le tag `beta`/`canary`), choisir le canal Stable propose la dernière Stable même si elle est numériquement inférieure — `GET /api/updates/check` renvoie alors `is_downgrade: true` et Réglages affiche « Revenir à la version Stable ». La planification quotidienne n'applique **jamais** un retour arrière : seul le bouton le fait.
- **Interrogation GitHub** : réponse mise en cache par canal avec `ETag` (une requête conditionnelle `304` ne consomme pas le quota partagé du réseau), repli sur la dernière réponse connue pendant la courte fenêtre où la CI supprime puis recrée la release `beta`/`canary`, et codes d'erreur distincts (`offline`, `rate_limited`, `not_found_*`) au lieu d'un « hors ligne » générique. `?refresh=1` contourne la fenêtre anti-doublon (clic explicite, changement de canal).
- **Choix de l'asset** : par profil (extension) et, sur Android, par variante (`Bobine-<v>.apk` téléphone/tablette vs `Bobine-TV-<v>.apk`, deux `applicationId` distincts). Empreinte SHA-256 obligatoire (fail-closed) sur tous les profils non-git, Android compris.
- **Téléchargement** : fichier `.part`, trois tentatives, contrôle de l'espace disque, renommage atomique seulement après vérification de l'empreinte.
- **État après redémarrage** : un service qui se relance pour appliquer la mise à jour ne peut pas écrire « terminé ». `update_orchestrator` enregistre l'empreinte `version|commit` avant la mise à jour et, au démarrage suivant, conclut « terminé » si elle a changé, « échec » sinon (`load_persisted_state_at_startup`). Aucun `force_reload` n'est diffusé au début du pipeline : les clients se rechargent d'eux-mêmes via le changement de `boot_id`.
- **Headless** : retour arrière automatique (`git checkout` de la référence précédente) si l'installation des dépendances ou la compilation du frontend échoue ; délais allongés pour un Dell Wyse 5070.
- **Android** : `AndroidHandler` obtient le contexte via `Python.getPlatform().getApplication()` (`PyApplication.context` n'existe pas — cause racine de l'échec « Impossible de déclencher la mise à jour Android »). `UpdateManager.kt` télécharge, vérifie l'empreinte, contrôle paquet/signature/`versionCode` (Android interdit tout retour en arrière sans désinstaller : message explicite plutôt que « application non installée »), puis propose l'installation via une notification qui porte directement l'intention d'installation. Il ne télécharge plus rien spontanément au lancement de l'application.
- **Environnement assaini des sous-processus système (2026-10-16)** : `update_orchestrator.clean_subprocess_env()` retire (ou restaure depuis `LD_LIBRARY_PATH_ORIG`) le `LD_LIBRARY_PATH` que PyInstaller positionne pour `BobineBackend` lui-même, avant tout appel à un binaire système externe (`systemctl`, `dpkg`, `git`) — sans ça, `systemctl --user restart bobine.service` charge la `libcrypto.so.3` bundlée (plus ancienne) au lieu de celle de l'hôte et échoue avec un symbole OpenSSL manquant. Appliqué dans `run_checked()` et dans le `Popen` détaché de `restart_services()`.
- **Redémarrage `.deb` non bloquant (2026-10-16)** : `apply_update()` du profil `linux-desktop` délègue désormais le redémarrage final à `restart_services()` (tâche détachée + `os._exit(0)` différé) plutôt que d'attendre un `systemctl --user restart` synchrone — ce process EST la cible du restart, et l'attendre bloquant l'exposait à être tué par systemd en plein milieu de l'attente.
- **Verrou anti-double-instance (2026-10-16)** : `tray.py::_acquire_single_instance_lock()` (bind TCP exclusif sur un port dédié, portable Windows/Linux/macOS, relâché automatiquement par l'OS même en cas de crash) empêche deux `BobineTray` de superviser chacun leur propre arbre `BobineBackend` — `postinst` peut relancer Bobine par deux voies concurrentes après une mise à jour `.deb` (`systemctl --user restart` + repli `nohup` si son `pgrep` de contrôle s'exécute trop tôt), doublant la RAM utilisée le temps que le doublon soit détecté. Sentinelle `/tmp/bobine-self-update-in-progress` posée par `apply_update()` autour de `pkexec dpkg -i` : `packaging/linux/DEBIAN/prerm` ne tue plus `BobineBackend` quand c'est lui-même qui pilote la mise à jour en cours.
- **Acquittement persisté de la notification (2026-10-16)** : `acknowledged_started_at` (champ serveur, `update_orchestrator.acknowledge_current()` / `POST /api/updates/acknowledge`) remplace l'ancien state React local `dismissed`, qui revenait à `null` — et faisait réapparaître la bannière — à chaque rechargement de page ou redémarrage de service déclenché par la mise à jour elle-même.
- **Étape `verifying` effectivement émise (2026-10-16)** : `download_with_progress()` accepte un callback `on_verifying`, appelé juste avant la comparaison d'empreinte SHA-256 — cette étape, définie dans `UpdateStep` depuis le début, n'était jamais réellement signalée au frontend.

### Autorisation sudo restreinte & désinstallation depuis l'interface

`install.sh` écrit `/etc/sudoers.d/bobine` autorisant **sans mot de passe, et uniquement**, deux actions déclenchées depuis l'admin :

- le **redémarrage** des services (`systemctl restart`) — bouton « Synchronisation des écrans » (Paramètres → Maintenance) : chaque écran connecté **vide son cache navigateur** puis se recharge (re-télécharge les nouveaux assets), et le backend + le kiosque sont relancés. À utiliser après une mise à jour des médias ou en cas de comportement bloqué ;
- l'enveloppe de **désinstallation** `/usr/local/sbin/bobine-uninstall` — bouton « Désinstaller » (Paramètres → **Zone de danger**). L'enveloppe détache la remise à zéro via `systemd-run` (pour survivre à l'arrêt du service backend) puis exécute `install.sh --uninstall --purge --purge-data -y` : arrêt/suppression des services + config `/etc` + application + venv + **toutes les données** (les paquets `apt` partagés sont conservés). L'UI exige de recopier la phrase « DÉSINSTALLER » ; hors machine installée (poste de dev), l'endpoint refuse proprement.

---

## 8. Référence API HTTP & WebSockets

### Endpoints HTTP (`/api`)

| Domaine | Préfixe | Description |
|---|---|---|
| **Vidéos** | `/api/videos` | Import, liste, détail, normalisation, suppression et catégories distinctes (`/videos/programs`) |
| **Sous-titres & Chapitres** | `/api/videos/{id}/subtitles`, `/api/videos/{id}/chapters` | Pistes `.srt`/`.vtt` (diffusion `GET .../subtitles/{sub_id}/vtt`) ; chapitres (`GET/PUT`, `POST .../import`, `POST .../from-file`, `GET .../export`) |
| **Playlists Vidéo** | `/api/playlists` | Gestion des playlists vidéo (CRUD, relecture) |
| **Fonds Animés** | `/api/backgrounds` | Gestion de la bibliothèque de boucles visuelles |
| **Audio Coach** | `/api/audio` | Import de cours audio (MP3/ZIP), gestion des pistes |
| **Playlists Audio** | `/api/audio-playlists` | Playlists mixtes audio coach avec fonds |
| **Planning** | `/api/schedule` | Programmateurs, occurrences et exceptions |
| **Lecture** | `/api/playback` | Contrôle de la lecture (play, pause, seek, stop, reprise) |
| **Écrans** | `/api/display` | `GET/PUT /display/state` : nombre d'écrans externes remonté par chaque plateforme et mode d'affichage câblé effectif (cf. « Projection HDMI plug-and-play ») |
| **Paramètres** | `/api/settings` | Configuration dynamique (lecture/thème/langue/`deployment_profile`/`update_channel`), sortie vidéo, espace de stockage (`/settings/storage`), synchronisation des écrans (`POST /settings/system/reset` — vidage des caches + rechargement + relance des services), sauvegarde & restauration universelles ZIP (`/settings/system/backup`, `/settings/system/restore`), et réinitialisation usine ou désinstallation machine (`POST /settings/system/reset-data`, `POST /settings/system/uninstall`, phrase de confirmation requise) |
| **Mises à jour** | `/api/updates` | `GET /updates/check` — interroge GitHub Releases selon le canal de mise à jour courant (Stable/Bêta/Canary, cf. §7) et le profil de déploiement pour l'asset adapté ; `POST /updates/apply` — déclenche `git checkout <tag>` + redémarrage (profil headless uniquement, 400 sinon) |
| **Imports** | `/api/import-jobs` | File d'attente des tâches d'importation (`GET /api/import-jobs` avec pourcentage, ETA en secondes et vitesse) et annulation réactive (`DELETE /api/import-jobs/{id}` avec arrêt FFmpeg et purge) |
| **Logs** | `/api/logs` | Consultation et téléchargement des journaux système |
| **Périphériques** | `/api/devices` | `GET /status` (public : activation, PIN défini, accès, capacités une fois accordé) ; `POST /session` / `DELETE /session` (PIN → cookie) ; local uniquement : `POST /admin/enable`, `POST/DELETE /admin/pin` ; derrière l'accès : `/audio` (`/default`, `/volume`), `/bluetooth` (`/power`, `/scan`, `/pair`, `/pairing/respond`, `/connect`, `/disconnect`, `/forget`, `/permission`), `/wifi` (`/scan`, `/power`, `/connect`, `/confirm`, `/forget`), `POST /system-settings` |
| **Radio — Bibliothèque** | `/api/radio` | Morceaux (CRUD, artistes/albums/tags), playlists radio, état d'une sortie (`/api/radio/state?channel=radio_cable\|radio_network`), son (`/api/radio/sound?channel=`), ambiance par défaut par sortie (`/api/radio/default-playlist`) |
| **Radio — Rappels** | `/api/radio/announcements`, `/api/radio/announcement-rules` | Annonces (import + description), règles de déclenchement, déclenchement manuel |
| **Métriques & Assiduité** | `/api/metrics` | Synthèse analytique du club (`GET /metrics/dashboard` avec filtres période et canal, KPIs satisfaction, complétion, affluence horaire 24h, classement des cours et télémétrie matérielle) et notation 5 étoiles (`POST /metrics/ratings`, `GET /metrics/ratings`) |

### WebSockets

- **Commandes client → serveur ajoutées en 4.0** : `subscribe` (`{channels: [...]}`, abonnement aux évènements propres à un canal), `time_sync` (`{t0}`, réponse directe `{event: "time_sync", t0, server_ms}` pour estimer le décalage d'horloge). Chaque `state_change` porte l'ancre d'horloge `clock`.
- `devices_changed` (`{scope}`) : évènement global sans donnée annonçant un changement d'audio, de Bluetooth ou de Wi-Fi (§5bis).
- `/ws/playback` : Diffusion en temps réel de l'état de lecture par canal — câblé, réseau **et radio** (`channel=radio_cable` ou `radio_network` ; l'ancien `radio` reste accepté en entrée, même connexion, vocabulaire de commandes `radio_*` propre au canal musical) — *position*, *durée*, *média courant*, décompte inter-cours. Diffuse aussi `library_change` (import/modification/suppression d'une vidéo — upload, dossier surveillé ou édition de titre) : `/grid`, `/cinema` et `/library` rechargent leur liste sans attendre leur sondage périodique.

---

## 9. Exploitation & Découverte Réseau (Wyse)

Sur le réseau local, la machine Wyse de production (`bobine-prod.local` / Dell Wyse 5070) reçoit son adresse IP via **DHCP**.

### Découverte mDNS embarquée (`bobine.local`)

`backend/app/utils/mdns.py` publie `bobine.local` via la bibliothèque `zeroconf` sur tous les
profils sauf : l'appliance headless (`avahi-daemon`, configuré par `install.sh`, s'en charge déjà)
et un Linux desktop où un `avahi-daemon` natif est détecté actif (`_avahi_daemon_active()`,
présence du socket `/var/run/avahi-daemon/socket` — fréquent, dépendance usuelle de
CUPS/NetworkManager) : publier en plus créerait un conflit de nom résolu silencieusement en
`bobine-2.local` (RFC 6762).

Boucle de fond (`_run_loop`), pas un enregistrement unique au démarrage :
- **Re-annonce périodique** (5 min, `_REANNOUNCE_INTERVAL_SECONDS`) : si l'IP locale a changé
  depuis la dernière annonce (DHCP, reconnexion Wi-Fi), `zc.update_service(...)` plutôt qu'un
  `ServiceInfo` figé sur l'IP du tout premier enregistrement.
- **Nouvelles tentatives à délai croissant** après un échec (`_RETRY_DELAYS_SECONDS`, 2s à 60s) —
  jamais d'abandon silencieux définitif jusqu'au redémarrage du backend.
- **État réel exposé** par `get_status()` (`"ok"`/`"failed"`/`"disabled"`/`"external"`/
  `"unavailable"`/`"pending"`), relayé dans `GET /api/settings` → `network.mdns_status` et affiché
  (icône d'avertissement) dans Réglages → Accès Réseau si `bobine.local` ne répond pas — avant ce
  champ, l'URL mDNS était une chaîne statique affichée comme fonctionnelle même après un échec de
  publication.

Android : `BobineForegroundService.kt` doit détenir un `WifiManager.MulticastLock` pour que les
paquets multicast (mDNS inclus) soient livrés au process applicatif — un
`ConnectivityManager.NetworkCallback` le ré-acquiert à chaque `onAvailable` (changement de réseau,
reconnexion) plutôt qu'une acquisition unique à `onCreate()`, certains pilotes radio
réinitialisant le filtrage multicast à la reconnexion.

### Protocole de Découverte Réseau (Si l'IP change)

1. **Test sur l'adresse courante ou le nom mDNS** (exemple d'IP documentaire ci-dessous, à remplacer par l'adresse réelle du site) :
   ```bash
   curl -s --connect-timeout 2 http://192.0.2.10:8000/api/settings
   curl -s --connect-timeout 2 http://bobine-prod.local:8000/api/settings
   ```
2. **Scan Nmap automatique du sous-réseau** (si l'IP n'est pas joignable) :
   ```bash
   SUBNET=$(ip route | grep default | awk '{print $3}' | cut -d. -f1-3).0/24
   nmap -p 8000 --open "$SUBNET" -oG - | grep "8000/open"
   ```

### Commandes d'Exploitation à Distance (SSH)

```bash
# Vérifier l'état des services systemd sur la Wyse
ssh fanta@<WYSE_IP> "systemctl status bobine-backend bobine-kiosk"
```

### Déploiement sur la Wyse

**Attention : `git pull` ne fonctionne PAS sur la Wyse** : son réseau bloque GitHub entièrement (ports 22 **et** 443 vers github.com). Le dépôt `/home/fanta/Bobine` sur la Wyse **n'est pas un clone git** — le déploiement se fait par copie (`rsync`) depuis un poste de dev sur le même réseau local, jamais par `git pull` sur la machine cible elle-même.

```bash
# 1. Depuis le poste de dev, sur le même LAN que la Wyse — toujours en
#    --dry-run d'abord, vérifier qu'aucune ligne "deleting" ne touche data/ :
rsync -a --delete --dry-run \
  --exclude='.git/' --exclude='data/' --exclude='backend/data/' --exclude='backend/.venv/' \
  --exclude='frontend/node_modules/' --exclude='frontend/.next/' --exclude='frontend/out/' \
  --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.db*' --exclude='*.log' \
  --exclude='backend/.pytest_cache/' --exclude='VideoTest/' \
  ./ fanta@<WYSE_IP>:/home/fanta/Bobine/
# (puis sans --dry-run une fois vérifié)

# 2. Sur la Wyse : si le déploiement ajoute/modifie des dossiers média, des
#    réglages de config.toml ou des services systemd, relancer l'installateur
#    (idempotent, ne touche jamais data/ hors --uninstall --purge-data) :
ssh fanta@<WYSE_IP> "cd /home/fanta/Bobine && sudo ./install.sh --skip-packages -y"
# Pour un changement de CODE SEUL (aucun nouveau dossier/réglage/service),
# un simple rebuild suffit à la place de l'étape ci-dessus :
#   ssh fanta@<WYSE_IP> "cd /home/fanta/Bobine/frontend && npm run build"

# 3. install.sh ne redémarre PAS un service déjà actif : redémarrage explicite
#    pour charger le nouveau code (ces deux commandes sont NOPASSWD) :
ssh fanta@<WYSE_IP> "sudo -n systemctl restart bobine-backend.service && sudo -n systemctl restart bobine-kiosk.service"

# 4. Vérifier : santé de l'API, services actifs, espace disque de data/ inchangé
ssh fanta@<WYSE_IP> "curl -s localhost:8000/api/health; systemctl is-active bobine-backend bobine-kiosk; du -sh /home/fanta/Bobine/data"
```

Les commits restent locaux jusqu'à ce qu'une machine avec accès GitHub (hors LAN de la Wyse) les pousse sur `origin/main` — le déploiement ne dépend jamais de ce push.

---

## 10. Matrice des interfaces & compatibilité multi-plateforme

Bobine repose sur une **interface frontend unique et unifiée** construite avec Next.js 16 (App Router) et exportée statiquement (`npm run build` → `frontend/out`). Cette interface est partagée et embarquée de manière identique sur **tous les profils de déploiement**.

### 10.1 Cartographie des 21 routes de l'interface (+ `/` redirigeant vers `/dashboard-cable`)

| Catégorie | Route(s) | Description & Particularités multi-OS |
|---|---|---|
| **Diffusion & Kiosque** | `/kiosk` | Kiosque automatique plein écran (programmation, inter-cours, démarrage direct sans délai). Horloge avec `suppressHydrationWarning`, synchronisation réseau (`/api/time`), overlay de pause cinématique Netflix avec vignette média et description normalisée. |
| | `/cinema` | Vitrine de sélection « Apple TV » avec héros en glassmorphism centré, rangées par catégorie, télécommande HID et **Moteur Vidéo Gapless A/B Deck** (double décodeur sans écran noir). Écran de pause Netflix avec miniature interactive, description scrollable sans rupture de phrase, et sélecteur de pistes de sous-titres (.vtt / .srt) translucide aux couleurs du thème. En mode Pupitre Studio double écran (`dual_screen`), l'écran externe affiche un écran de veille passif *« En attente d'un cours »* pendant que la sélection s'opère sur la console tactile `/grid` ; en mode Headless (`headless`), l'écran externe présente directement la grille interactive complète. Notation 5 étoiles sur l'écran de fin. |
| | `/grid` | Interface de sélection tactile et régie dédiée (tablettes Android, ordinateurs portables en mode Pupitre Studio). **Pilote exclusivement le canal câblé (HDMI)** (aucun équivalent réseau, administré via `/dashboard-network`). Supporte la navigation tactile, souris, télécommandes HID et manettes de jeu avec anti-rebond et lissage monotone du temps. Évaluation 5 étoiles tactile à la fin du cours (cf. § 10.2 ci-dessous). |
| **Régies & Contrôle** | `/dashboard-cable`<br>`/dashboard-network` | Tableaux de bord de contrôle indépendant pour les canaux Câblé et Réseau (déclenchement direct, reprise, volume, diffusion d'ambiance visuelle 1-clic) équipés d'une barre de bascule segmentée Câblé / Réseau animée (grossissement au survol, lueur de sélection spéculaire). Redirection automatique transparente de `/dashboard-cable` vers `/coach` lorsque le mode coach est actif. |
| **Console Régie Coach** | `/coach` | Console régie studio responsive : double colonne sur tablette paysage et desktop avec lecteur tactile surdimensionné, minuteur, playlist déroulante intégrée, **Stage Monitor 16:9** (retour HDMI direct de salle) et **Palette tactile d'ambiances 16:9** avec switch live 1-clic. Version compacte monoposte avec tiroirs tactiles sur mobile. |
| **Administration** | `/settings` | Gestionnaire de configuration : 16 thèmes (dont la paire minérale « Charbon » / « Charbon Sombre », clair et sombre, certifiés WCAG AA/AAA), sélecteur de mode d'affichage câblé (Pupitre Studio double écran vs Headless), actualisation réseau dynamique (polling 15s + bouton manuel), supervision complète (CPU, GPU, RAM, Stockage, Puissance en W, Températures, Uptime), sauvegarde/restauration ZIP. |
| | `/metrics`<br>`/metrics/courses`<br>`/metrics/system` | Tableau de bord analytique et assiduité (Bêta 3.0.5) : 4 indicateurs clés (satisfaction moyenne 5★, taux de complétion ≥90%, volume de diffusion en heures, nombre de séances), histogramme 24h d'affluence horaire CSS pur, palmarès des cours plébiscités, télémétrie matérielle temps réel, base EAV et tiroir d'historique (1h, 6h, 24h, 7j). |
| | `/library` | Bibliothèque vidéo avec métadonnées, durée et upload universel de miniatures personnalisées (`PUT /api/videos/{id}/thumbnail` via Pillow, sans dépendance ffmpeg). |
| | `/backgrounds` | Hub d'Ambiances Visuelles (Bêta 3.0.5) : gestion centralisée des boucles d'ambiance 16:9 avec prévisualisations vidéo au survol, projection directe sur sorties Câblée et Réseau, lecteur modal immersif et configuration du fond par défaut pour les cours coach. |
| | `/audio`<br>`/audio-playlists` | Bibliothèque audio coach et gestionnaire de playlists avec sélecteur visuel d'ambiance 16:9 modal et assignation dynamique. |
| | `/playlists`<br>`/schedule`<br>`/logs` | Gestion des listes ordonnées, programmation horaire récurrente (APScheduler) et inspection des journaux système. |
| | `/devices` | Périphériques : audio, Bluetooth et Wi-Fi de la machine, accès par PIN à distance, section Sécurité réservée à l'écran local (§5bis). |
| **Sorties radio** | `/radio?channel=cable`<br>`/radio?channel=network`<br>`/radio` (alias réseau)<br>`/radio-announcements`<br>`/radio-library`<br>`/radio-remote` | Canal sonore continu indépendant avec enchaînement musical Web Audio API, ducking automatique et rappels vocaux de bienséance. |

---

### 10.2 Intégration et montage par profil de déploiement

Le serveur FastAPI (`backend/app/main.py`) monte dynamiquement le dossier statique selon le profil exécuté via la classe `RevalidateStaticFiles` (injectant `Cache-Control: no-cache` pour forcer la revalidation ETag et éviter tout gel heuristique du cache HTTP) :

| Profil | Cible & Format | Emplacement frontend servi | Consommateur principal de l'UI |
|---|---|---|---|
| **Headless Appliance** | Dell Wyse / Mini PC (`install.sh`, Debian 13) | `frontend/out/` (relatif au dépôt) | Kiosque Chromium X11 (`/kiosk` et/ou `/cinema`) + navigateur distant pour l'admin |
| **Windows Desktop** | Windows 10/11 (`.exe` Inno Setup) | `%ProgramFiles%\Bobine\frontend\out\` | Navigateur web par défaut au lancement + icône de notification en barre des tâches (systray). Supporte le mode Pupitre Studio (double écran) ou Headless (clamshell). |
| **macOS Desktop** | macOS Apple Silicon (`.dmg` / `Bobine.app`) | `Bobine.app/Contents/Resources/frontend/out/` | Navigateur web par défaut + menu bar companion. Supporte le mode Pupitre Studio ou Clamshell capot fermé. |
| **Linux Desktop** | Debian/Ubuntu/Mint (`.deb` / `apt.bobine.fit`) | `/usr/lib/bobine/frontend/out/` | Navigateur web par défaut + systray XDG. Supporte le mode Pupitre Studio ou Clamshell capot fermé. |
| **Tablette Android / Android TV** | Tablettes ARM64 (`.apk`, Chaquopy, Python 3.13) ; boîtiers Android TV ARM 32/64 bits (`Bobine-TV-*.apk`, Python 3.11) | Assets embarqués `pyStage/backend/frontend_out/` | Double WebView matérielle : tactile local (`/grid` ou accueil) + affichage externe HDMI (`/cinema`) |

Sur le profil Android, les données sont réparties sur **deux racines de stockage** distinctes (`backend/app/config.py::_android_internal_root()`) — la base SQLite, les miniatures, les logs, le branding et les pochettes radio vivent sur le stockage **interne** de l'app (`context.filesDir`, f2fs natif) tandis que les médias (vidéos, fonds, audio, radio) restent sur le stockage **externe** (`context.getExternalFilesDir`, servi par FUSE, visible depuis un gestionnaire de fichiers). Une installation existante est migrée automatiquement et sans risque de perte (copie, jamais de déplacement destructif, vérification `PRAGMA integrity_check` avant utilisation) au premier démarrage qui suit une mise à jour — cf. `android/app/src/main/python/bobine_bootstrap.py`.
| **Assistant GUI** | Linux x86_64 (`bobine-assistant`, Tauri 2 / Rust) | `assistant/ui/` (intégré au binaire Rust) | Fenêtre native GTK WebKit pour la découverte mDNS, scan LAN et déploiement SSH |

**Variante Android TV et ABI 32 bits.** Beaucoup de boîtiers et clés Android TV (Chromecast avec Google TV, Xiaomi TV Stick/Box) ont un processeur 64 bits mais un système 32 bits : leur liste d'ABI est `armeabi-v7a` seule, et un APK sans dossier natif `lib/armeabi-v7a` y échoue avec `INSTALL_FAILED_NO_MATCHING_ABIS`. Chaquopy ne fournit le runtime `armeabi-v7a` que jusqu'à Python 3.11 (Maven Central : `target:3.13.9-0` n'a que `arm64-v8a` et `x86_64`). Le flavor `tv` embarque donc Python **3.11** avec les ABI `armeabi-v7a`, `arm64-v8a` et `x86_64` (`chaquopy.productFlavors` dans `android/app/build.gradle.kts`) ; le flavor `mobile` reste en Python 3.13 (`arm64-v8a`, `x86_64`). Conséquences à connaître :

- Le runtime 3.11 ne répond ni `platform.system() == "Android"` ni `sys.getandroidapilevel` : toute détection d'Android passe par `app.utils.android_runtime.is_android()` (marqueur `BOBINE_PLATFORM` posé par `bobine_bootstrap.py`, variables du zygote `ANDROID_ROOT`/`ANDROID_DATA`, signaux CPython 3.12+). Ne jamais tester `platform.system()` ou `getandroidapilevel` seuls.
- Le backend doit rester compatible Python 3.11 (pas de f-string aux guillemets imbriqués, ni de syntaxe ou d'API postérieure) : le job `backend` de la CI le teste en 3.11, 3.12 et 3.13.
- `ffmpeg`/`ffprobe` armeabi-v7a sont compilés depuis les sources officielles (`android/scripts/build_ffmpeg_armv7.sh`, NDK r28c, build LGPL avec MediaCodec) car aucun binaire 32 bits n'est publié ; la CI les met en cache.
- `scripts/ci/verify-apk-abis.sh` contrôle les ABI et binaires embarqués de chaque APK avant publication.

### 10.3 Compatibilité navigateurs (Firefox / Gecko)

<img src="../Assets/Images/firefox.svg" alt="Firefox" width="40" align="left" hspace="10" /> Bobine soutient le projet Firefox : l'interface d'administration et les lecteurs ouverts depuis d'autres appareils (`/radio`, `/kiosk`, `/cinema`, `/coach`) ciblent Firefox (version courante, précédente et ESR ; bureau et Android) au même titre que les moteurs Chromium et WebKit.

- **Règle d'ingénierie** : détection de fonctionnalités uniquement (jamais `navigator.userAgent`) ; aucun code spécifique à un navigateur.
- **Vérifié sur Firefox 157** : WebSocket, XHR/`FormData` (upload), `Range` (206, plage suffixe), CORS, Web Audio, Gamepad, Wake Lock, `requestVideoFrameCallback`, `webkitdirectory`, Cache API. Lecture H.264 (jusqu'à 1080p60 à 60 Mbit/s) sans image perdue ; HEVC/AV1 dépendent de l'OS et du matériel.
- **Livré en 4.0.3** : flux média conformes RFC 9110 (`HEAD`, `Range`, `If-Range`, `416`, `ETag` — `app/utils/media_response.py` ; plus aucun `/api/*` ne renvoie du HTML) ; **téléversement par morceaux reprenable** (`/api/uploads`, `app/utils/staged_uploads.py`, client `frontend/src/lib/chunkedUpload.ts`) ; filtre de dépôt par extension ; `ffmpeg` à priorité réduite sur les profils où le navigateur partage la machine ; **version web « lisible partout »** (H.264 8 bits ≤ 1080p, `app/utils/web_profile.py`, négociation `?accept=` sur `/api/videos/{id}/stream`, original jamais modifié) ; Réglages → Compatibilité navigateur.
- **Reste ouvert** : HTTPS local optionnel (Wake Lock et Gamepad exigent un contexte sécurisé — `http://<ip>` du LAN) ; mesures Windows/macOS/Android/ESR.
- **Crash/lag d'import signalé** : identifié par le mainteneur comme une fuite mémoire d'un autre logiciel du poste, hors Bobine (cohérent avec nos mesures : rien de reproduit avec 31 fichiers / 1,5 Go, lien limité à 32 Mbit/s, 2 cœurs).
- Banc de mesure reproductible : [`scripts/browser-bench/`](../scripts/browser-bench/README.md).

<br clear="left"/>

---

## 11. Licence

Bobine est distribué sous licence **GNU AGPL-3.0** (voir [`LICENSE`](../LICENSE) à la racine). Toute mise à disposition du logiciel, y compris via un service accessible en réseau, impose de publier le code source correspondant (y compris vos modifications) sous la même licence.

