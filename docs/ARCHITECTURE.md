# Bobine — Architecture technique & référence développeur

> Référence technique. Pour une présentation orientée utilisateur (à quoi sert Bobine, installation guidée, prise en main), voir le **[README](../README.md)** (`README.fr.md` pour le français).

Diffusion, planification et pilotage de vidéos de cours en salle, sur mini PC dédié. Serveur FastAPI mono-processus + SQLite, kiosque Chromium X11, interface d'administration et télécommande mobile Next.js.

Ce document est écrit pour quiconque souhaite **comprendre, exploiter, modifier ou déployer** le système Bobine : il décrit l'architecture réellement en place (pas une intention), le contrat réseau, le modèle de données, ainsi que la configuration d'exploitation sur mini PC dédié.

---

## Sommaire

1. [Stack et démarrage](#1-stack-et-démarrage)
2. [Architecture générale](#2-architecture-générale)
3. [Modèle de données & Persistance SQLite](#3-modèle-de-données--persistance-sqlite)
3bis. [Pipeline d'importation, Accélération Matérielle Multi-OS & Annulation Réactive](#3bis-pipeline-dimportation-accélération-matérielle-multi-os--annulation-réactive)
4. [Canaux de diffusion & Gestionnaire de lecture](#4-canaux-de-diffusion--gestionnaire-de-lecture)
5. [Module Radio](#5-module-radio)
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
- **Frontend** : [Next.js](https://nextjs.org/) 16 (App Router, export statique servi par le backend en production), React 19, TypeScript, CSS Vanilla (global + design tokens, **16 thèmes de couleurs** commutables à chaud via `:root[data-theme=…]`, dont la paire minérale « Charbon » / « Charbon Sombre » (clair et sombre, tous deux certifiés WCAG AA/AAA), PWA (`manifest.json`), WebSockets, glisser-déposer natif (HTML5), Web Audio API.
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
- `routers/` : Endpoints HTTP groupés par domaine (`videos`, `backgrounds`, `playlists`, `audio`, `audio_playlists`, `schedule`, `playback`, `settings`, `logs`, `import_jobs`, `radio`, `radio_playlists`, `radio_announcements`).

---

## 3. Modèle de données & Persistance SQLite

Le schéma de données est géré par **SQLAlchemy**. Il n'y a **pas d'Alembic actif** dans ce projet (dossier `alembic/versions/` vide) : les tables sont créées par `Base.metadata.create_all()` au démarrage, et l'ajout de colonnes sur des tables existantes passe par des micro-migrations idempotentes dans `database.py::_migrate_add_missing_columns`. Stockage dans un fichier SQLite unique (`data/database.db`).

### Entités principales

- `videos` / `backgrounds` : Métadonnées des médias (durée, résolution, codec, description/synopsis, fps, bitrate, canaux audio et codec audio, vignettes générées dans `data/thumbnails`).
- `playlists` & `playlist_items` : Playlists de cours vidéo ordonnées.
- `audio_courses` & `audio_tracks` : Cours audio importés et leurs pistes associées.
- `audio_playlists` & `audio_playlist_items` : Éditions mixées audio coach avec attribution de fond visuel par piste.
- `schedules` & `schedule_overrides` : Programmations récurrentes ou ponctuelles, avec gestion des exceptions d'occurrences (annulation, remplacement).
- `playback_state` : État de lecture persisté par canal (*Câblé* et *Réseau*), incluant la sauvegarde des actions interrompues pour la reprise automatique.
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

## 4. Canaux de diffusion & Gestionnaire de lecture

Le système pilote deux canaux de diffusion vidéo **strictement indépendants**, plus un 3ᵉ canal musical (§5) :

1. **Canal Câblé (`channel=cable`)** : Canal d'affichage principal relié à la sortie vidéo physique du mini PC (écran salle / kiosque).
2. **Canal Réseau (`channel=network`)** : Canal secondaire destiné à la diffusion réseau ou aux écrans auxiliaires.
3. **Canal Radio (`channel=radio`)** : 3ᵉ canal, totalement indépendant des deux premiers (aucune interaction) — diffusion musicale continue sur un poste dédié. Géré par un gestionnaire d'état séparé (`radio_manager.py`), pas le `playback_manager` ci-dessous.

Chaque écran affiche `/kiosk` ou `/cinema` selon la sortie choisie par l'admin (`/api/settings/display-output`, ex. câble → `cinema`, réseau → `kiosk`). L'écran câblé (`127.0.0.1`, détecté par `isWiredDisplay()`) suit toujours sa sortie stockée. **Bibliothèque vide** : `/cinema` affiche un écran d'attente plein écran (grand logo + heure + « Aucun cours disponible ») au lieu d'un écran noir ; `/kiosk` a son propre écran d'attente (horloge + prochain cours). Les **catégories de cours** sont des libellés **libres** (plus de RPM/Sprint/The Trip figés) : saisie avec suggestions des catégories déjà utilisées, filtre et regroupement dynamiques.

**Télécommandes physiques** (réf. hook `useKioskRemote`) : `/cinema` et `/radio` (PAS `/kiosk` ni l'admin) réagissent à une télécommande USB à dongle (présentateur / « air remote » média), vue comme un **clavier HID** — Chromium délivre ses touches en `keydown`, aucun pilote ni appairage. Mapping : flèches + OK pour parcourir la vitrine (sélection par classe `.kiosk-remote-focus` posée en JS plutôt que `:focus`, car un kiosk n'a pas toujours le focus fenêtre OS) et lancer un cours ; Espace/Play-Pause, pistes précédente/suivante, volume et touches média pour le transport. Sur `/radio`, une touche sert aussi de geste de déverrouillage de l'audio.

### Reprise après interruption (Resilience Rule)

Lorsqu'une programmation automatique (`scheduler`) doit démarrer alors qu'une lecture manuelle est en cours :
1. Le `playback_manager` interrompt la lecture manuelle et sauvegarde la position exacte et l'identifiant du média dans `playback_state`.
2. Le cours programmé s'exécute.
3. À la fin de la programmation, l'interface propose automatiquement la **reprise à la seconde près** du cours interrompu.

### Récupération d'un décodeur vidéo bloqué (`/kiosk`, `/cinema`)

Sur certains décodeurs matériels (MediaCodec sur Android, VA-API sur Linux/Wyse), un seek vers une position hors keyframe à chaud pouvait laisser le pipeline vidéo désynchronisé ou bloqué sur la dernière image décodée alors que la piste audio continuait d'avancer — l'écran affichait une image figée alors que le son et l'horloge progressaient. Quatre protections complémentaires et coordonnées couvrent ce cas dans `/kiosk` et `/cinema` :
1. **Seeks protégés et synchronisation pause/seeked** : toute assignation de `currentTime` passe par `seekWhenReady()`. Si l'élément est en cours de lecture, il est temporairement mis en pause pour figer l'horloge audio avant le saut temporel, puis relancé uniquement à la réception de l'événement `seeked` (avec timeout de secours à 1200 ms). Cela garantit que l'audio ne devance pas la reconstitution du GOP vidéo.
2. **Garde anti-réentrance** : interdiction de déclencher un nouveau seek tant que `el.seeking` est actif, évitant l'écrasement perpétuel du buffer décodeur.
3. **Période de grâce après seek (3 000 ms)** : sur les kiosques miroirs (réseau ou multi-écrans), les recalages périodiques de `position_tick` sont ignorés pendant 3 secondes après un seek pour laisser les tampons et l'affichage se stabiliser.
4. **Watchdog réactif via `requestVideoFrameCallback`** : un contrôle régulier surveille le nombre d'images réellement peintes à l'écran (`presentedFrames`) avec repli sur `currentTime`. Si un gel effectif de rendu est détecté en cours de lecture (`visualFreeze`), un micro-seek (+0,05s) avec cycle pause/play sur `seeked` débloque automatiquement la texture d'affichage.

---

## 5. Module Radio

Sous-système musical « type Spotify » **totalement indépendant** des cours vidéo/audio coach (canal `radio` dédié, tables `radio_*`, gestionnaire d'état `radio_manager.py`) — bibliothèque, playlists, lecture continue, crossfade et rappels sonores.

- **Surfaces** : `/radio` (écran du poste dédié — affichage + contrôles, ouvert à la main dans un navigateur, pas de service kiosk systemd), onglet admin « Radio » (télécommande à distance sur `/radio-remote`), « Piste Audio Radio » (bibliothèque sur `/radio-library`), « Rappels » (annonces sur `/radio-announcements`), et un 3ᵉ onglet « Radio » sur la page Planning (`/schedule/?channel=radio`). Hors diffusion (écran d'attente + overlay « Démarrer la radio »), le poste affiche un **grand logo plein écran** (fond opaque du thème) ; déverrouiller le poste **ne lance aucune musique** tant qu'aucune radio n'est réellement active (état `idle`), pour ne pas désynchroniser l'interface admin.
- **Bibliothèque** : import tous formats audio (transcodage automatique de ce que le navigateur ne lit pas), pochettes extraites (ID3) ou manuelles, navigation par artiste/album/tags. L'écran admin « Piste Audio Radio » (`/radio-library`) est une **vue d'ensemble** : barre latérale de filtres (playlists / tags / genres / artistes), grille à sélection multiple avec actions groupées (taguer, ajouter à une playlist), tags éditables en chips, éditeur de playlist en glisser-déposer.
- **Lecture** : continue, file d'attente, lecture aléatoire, répétition (piste/playlist), **crossfade** (Web Audio API — deux `<audio>` routés dans un graphe `MediaElementAudioSourceNode → GainNode → destination`, fondu démarré côté client en avance sur la confirmation serveur).
- **Rappels** : annonces de bienséance avec description, règles de déclenchement (toutes les N musiques / toutes les X minutes / à heures fixes / manuel), insertion en attente de fin de piste ou par fondu immédiat (« duck » — réutilise le même graphe Web Audio que le crossfade). Chaque rappel est **normalisé en loudness à l'import** (`ffmpeg loudnorm` EBU R128, 2 passes, cible -10 LUFS) pour s'entendre au moins aussi fort que la musique. Écran d'admin dédié (`/radio-announcements`) : import, activation, règles, déclenchement manuel.
- **24/7 & Planning** : une playlist marquée par défaut (`is_default`) tourne en boucle en permanence ; auto-démarrage au boot (`radio_autostart_on_boot`). **Sans aucune playlist par défaut, le repli joue toute la bibliothèque en aléatoire et en boucle** (playlist virtuelle « Toute la bibliothèque », `playlist_id=None`, recomposée à chaque lancement donc toujours à jour avec la bibliothèque) : la radio n'est jamais muette au démarrage sans qu'il faille créer une playlist ; définir une `is_default` reprend la priorité. Le Planning peut y superposer des fenêtres horaires récurrentes (option 24/7) qui, en fin de fenêtre, reviennent à l'ambiance par défaut — ou, à défaut, à ce même repli bibliothèque plutôt qu'au silence.
- **Config** (`radio_dir`, `radio_covers_dir`, `radio_announcements_dir`, `radio_watch_dir`, `radio_volume_default`, `radio_crossfade_seconds`, `radio_announcement_duck_level`, `radio_announcement_fade_ms`, `radio_autostart_on_boot`) : voir `config.py` — dossiers unifiés sous `${REPO_DIR}/data` par `install.sh` comme le reste des médias.

---

## 6. Mode Audio Coach & Fonds animés

Le mode **Audio Coach** permet de diffuser des cours audio (pistes vocales / musique) sur l'équipement sonore de la salle tout en affichant un fond visuel dynamique sur l'écran.

- **Importation** : Support des fichiers MP3 individuellement ou par paquets ZIP.
- **Fonds animés** : Boucles vidéo stockées dans `data/backgrounds` (arbre média unifié sous `${REPO_DIR}/data`), jouées en boucle infinie sans coupure.
- **Minuteur d'enchaînement (`audio_chain_timer_seconds`)** : Délai de transition configurable entre deux pistes audio (modifiable depuis `/api/settings`).
- **Lancement** : une playlist audio coach se lance depuis la page « Cours Audio » (`/audio`, actif uniquement quand le câblé est **déjà** en mode coach — sinon on passe d'abord par « Passer en mode coach » / `/coach`) ou directement depuis l'écran mobile `/coach`. Le raccourci autrefois présent sur le tableau de bord câblé a été déplacé ici.

---

## 7. Script d'installation & Services systemd

L'installation de production s'effectue via le script shell idempotent `install.sh` sur Debian 13 (Trixie).

```bash
# Installation complète sur la machine cible
sudo ./install.sh
```

### Options d'installation (`sudo ./install.sh --help`)

| Option | Description |
|---|---|
| `--no-kiosk` | Installation du backend seul (sans Chromium X11 / audio) |
| `--dry-run` | Prévisualisation des actions sans modification |
| `--check` | Diagnostic de l'installation existante |
| `--skip-packages` | Mise à jour du projet (après déploiement du code, §9) sans réinstaller les paquets `apt` |
| `--skip-build` | Ne reconstruit pas le frontend Next.js |
| `--as-user LOGIN` | Compte cible quand le script tourne en **root direct** (Debian **sans sudo**, lancé via `su -`) — cf. ci-dessous |
| `--channel=stable\|beta` | Canal de mise à jour (défaut `stable`) — cf. « Canal de mise à jour » ci-dessous |
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

Pas de service dédié pour le canal Radio (arbitrage A5, cf. §5) : `/radio` s'ouvre à la main dans un navigateur, sur le même backend.

### Assistant d'installation graphique

Une application graphique autonome (`assistant/`, développée avec **Tauri 2 / Rust**) tourne sur le **poste de l'administrateur** (Windows, macOS ou Linux), localise le mini PC sur le LAN (balayage `/24` de chaque interface réseau locale), s'y connecte en SSH, audite le matériel, puis **déroule `install.sh`** avec une barre de progression et un suivi temps réel des journaux d'installation. `install.sh` reste la **source de vérité unique** — l'assistant l'**orchestre**, il ne réimplémente rien. Détails complets et instructions de compilation : [`assistant/README.md`](../assistant/README.md).

Le scan réseau affiche **tous** les appareils qui répondent (pas seulement les cibles Bobine) — nom d'hôte, IP, indice d'OS, ports ouverts — pour qu'un utilisateur préparant un déploiement headless reconnaisse sa borne au milieu du reste du réseau. L'authentification SSH accepte, en plus du mot de passe, une clé privée importée explicitement via un sélecteur de fichier natif (`tauri-plugin-dialog`).

### Canal de mise à jour (Stable / Bêta)

Deux canaux, choisis à l'installation (`install.sh --channel=stable|beta`, ou dans le wizard de l'assistant Tauri) puis modifiables à tout moment depuis Réglages → Mises à jour ("Programme Bobine Beta") :

- **Stable** (défaut) : `GET /api/updates/check` interroge `/repos/.../releases/latest` — exclut structurellement les pre-releases côté API GitHub, donc ce canal ne peut jamais en recevoir une, même en cas de bug applicatif. Chaque version stable a son propre tag `Vx.y.z` et sa propre entrée sur GitHub Releases (historique normal).
- **Bêta** : interroge `/repos/.../releases/tags/beta` — un tag **unique et mobile**, republié en place à chaque publication plutôt qu'un nouveau tag par itération (`beta.1`, `beta.2`, … auraient fini par rendre la page Releases illisible). La détection de mise à jour compare le **commit** installé au commit visé par ce tag (`target_commitish`) — il n'y a pas de numéro de version qui avance à chaque build sur ce canal. Une version stable équivalente ou plus récente remplace toujours la bêta suivie.

Le choix est persisté (réglage `update_channel` en base pour le backend ; `/etc/bobine/update-channel` pour `install.sh`) et pilote aussi `apply_update()` du profil headless (bouton « Mettre à jour ») : `git checkout <tag>` plutôt qu'un `git pull --ff-only`, ce qui permet un vrai retour arrière (downgrade) vers un tag antérieur — et suit correctement un tag mobile (`git fetch --tags --force`).

Côté publication (`.github/workflows/ci.yml`) : le job `version` calcule à la fois le numéro de version (source de vérité unique : le fichier `VERSION` à la racine du dépôt) et le **canal**, structurellement séparés à partir de là :
- un tag `Vx.y.z` strict poussé → `release-stable` (nouvelle entrée GitHub Releases, `prerelease: false`, notes tirées de `docs/releases/<TAG>.md`, qui doit exister) ;
- un push direct sur `main` (hors tag), ou un déclenchement manuel (`workflow_dispatch`, case *publish_beta* cochée, depuis n'importe quelle référence — utile pour republier sans nouveau commit) → `release-beta` (force-déplace le tag `beta` sur le commit courant, supprime puis republie l'unique release Bêta, notes générées automatiquement — changelog depuis le dernier tag stable). La Bêta suit donc `main` en continu, sans jamais prendre de retard.

Les noms de fichiers des artefacts Bêta sont **fixes** (`Bobine-Setup-beta.exe`, `Bobine-beta.dmg`, `bobine_beta_amd64.deb`) — jamais de version ni de caractère `~` dedans (GitHub Releases réécrit silencieusement `~` en `.` dans les noms d'assets téléchargés). Le numéro de version *interne* (affiché dans l'app, champ `Version:` du paquet Debian) reste précis : `VERSION`/`COMMIT` sont bundlés dans chaque paquet (mêmes `datas` PyInstaller que `config.toml`) et lus au runtime par `app.utils.version` — y compris sur les profils packagés (Windows/macOS/Linux desktop), qui n'ont pas de `.git` pour se renseigner autrement.

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
| **Playlists Vidéo** | `/api/playlists` | Gestion des playlists vidéo (CRUD, relecture) |
| **Fonds Animés** | `/api/backgrounds` | Gestion de la bibliothèque de boucles visuelles |
| **Audio Coach** | `/api/audio` | Import de cours audio (MP3/ZIP), gestion des pistes |
| **Playlists Audio** | `/api/audio-playlists` | Playlists mixtes audio coach avec fonds |
| **Planning** | `/api/schedule` | Programmateurs, occurrences et exceptions |
| **Lecture** | `/api/playback` | Contrôle de la lecture (play, pause, seek, stop, reprise) |
| **Paramètres** | `/api/settings` | Configuration dynamique (lecture/thème/langue/`deployment_profile`/`update_channel`), sortie vidéo, espace de stockage (`/settings/storage`), synchronisation des écrans (`POST /settings/system/reset` — vidage des caches + rechargement + relance des services), sauvegarde & restauration universelles ZIP (`/settings/system/backup`, `/settings/system/restore`), et réinitialisation usine ou désinstallation machine (`POST /settings/system/reset-data`, `POST /settings/system/uninstall`, phrase de confirmation requise) |
| **Mises à jour** | `/api/updates` | `GET /updates/check` — interroge GitHub Releases selon le canal courant (Stable/Bêta, cf. §7) et le profil de déploiement pour l'asset adapté ; `POST /updates/apply` — déclenche `git checkout <tag>` + redémarrage (profil headless uniquement, 400 sinon) |
| **Imports** | `/api/import-jobs` | File d'attente des tâches d'importation (`GET /api/import-jobs` avec pourcentage, ETA en secondes et vitesse) et annulation réactive (`DELETE /api/import-jobs/{id}` avec arrêt FFmpeg et purge) |
| **Logs** | `/api/logs` | Consultation et téléchargement des journaux système |
| **Radio — Bibliothèque** | `/api/radio` | Morceaux (CRUD, artistes/albums/tags), playlists radio, état du canal (`/api/radio/state`) |
| **Radio — Rappels** | `/api/radio/announcements`, `/api/radio/announcement-rules` | Annonces (import + description), règles de déclenchement, déclenchement manuel |

### WebSockets

- `/ws/playback` : Diffusion en temps réel de l'état de lecture par canal — câblé, réseau **et radio** (`channel=radio`, même connexion, vocabulaire de commandes `radio_*` propre au canal musical) — *position*, *durée*, *média courant*, décompte inter-cours. Diffuse aussi `library_change` (import/modification/suppression d'une vidéo — upload, dossier surveillé ou édition de titre) : `/grid`, `/cinema` et `/library` rechargent leur liste sans attendre leur sondage périodique.

---

## 9. Exploitation & Découverte Réseau (Wyse)

Sur le réseau local, la machine Wyse de production (`pavilion-malefique` / Dell Wyse 5070) reçoit son adresse IP via **DHCP**.

### Protocole de Découverte Réseau (Si l'IP change)

1. **Test sur l'adresse courante ou le nom mDNS** :
   ```bash
   curl -s --connect-timeout 2 http://10.0.0.30:8000/api/settings
   curl -s --connect-timeout 2 http://pavilion-malefique.local:8000/api/settings
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
  --exclude='.claude/' --exclude='.agents/' --exclude='.gemini/' \
  --exclude='AGENTS.md' --exclude='CLAUDE.md' \
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

### 10.1 Cartographie des 18 routes de l'interface (+ `/` redirigeant vers `/dashboard-cable`)

| Catégorie | Route(s) | Description & Particularités multi-OS |
|---|---|---|
| **Diffusion & Kiosque** | `/kiosk` | Kiosque automatique plein écran (programmation, inter-cours, démarrage direct sans délai). Horloge avec `suppressHydrationWarning` et synchronisation réseau (`/api/time`). |
| | `/cinema` | Vitrine de sélection « Apple TV » avec héros, rangées par catégorie et télécommande HID. En mode Pupitre Studio double écran (`dual_screen`), l'écran externe affiche un écran de veille passif *« En attente d'un cours »* pendant que la sélection s'opère sur la console tactile `/grid` ; en mode Headless (`headless`), l'écran externe présente directement la grille interactive complète. |
| | `/grid` | Interface de sélection tactile et régie dédiée (tablettes Android, ordinateurs portables en mode Pupitre Studio). Permet de lancer et piloter la lecture sans superposition sur l'écran TV (cf. [`docs/cahier-des-charges-affichage-hybride.md`](cahier-des-charges-affichage-hybride.md)). |
| **Régies & Contrôle** | `/dashboard-cable`<br>`/dashboard-network` | Tableaux de bord de contrôle indépendant pour les canaux Câblé et Réseau (déclenchement direct, reprise, volume, fondu). |
| **Administration** | `/settings` | Gestionnaire de configuration : 16 thèmes (dont la paire minérale « Charbon » / « Charbon Sombre », clair et sombre, certifiés WCAG AA/AAA), sélecteur de mode d'affichage câblé (Pupitre Studio double écran vs Headless), actualisation réseau dynamique (polling 15s + bouton manuel), supervision CPU/RAM résiliente sous SELinux Android, sauvegarde/restauration ZIP. |
| | `/library` | Bibliothèque vidéo avec métadonnées, durée et upload universel de miniatures personnalisées (`PUT /api/videos/{id}/thumbnail` via Pillow, sans dépendance ffmpeg). |
| | `/playlists`<br>`/backgrounds`<br>`/schedule`<br>`/logs` | Gestion des listes ordonnées, fonds animés, programmation horaire récurrente (APScheduler) et inspection des journaux système. |
| **Mode Coach Audio** | `/audio`<br>`/audio-playlists`<br>`/coach` | Playlists musicales rythmées avec minutage automatique, décompte et association d'arrière-plans vidéo synchronisés. |
| **Canal Radio** | `/radio`<br>`/radio-announcements`<br>`/radio-library`<br>`/radio-remote` | Canal sonore continu indépendant avec enchaînement musical Web Audio API, ducking automatique et rappels vocaux de bienséance. |

---

### 10.2 Intégration et montage par profil de déploiement

Le serveur FastAPI (`backend/app/main.py`) monte dynamiquement le dossier statique selon le profil exécuté via la classe `RevalidateStaticFiles` (injectant `Cache-Control: no-cache` pour forcer la revalidation ETag et éviter tout gel heuristique du cache HTTP) :

| Profil | Cible & Format | Emplacement frontend servi | Consommateur principal de l'UI |
|---|---|---|---|
| **Headless Appliance** | Dell Wyse / Mini PC (`install.sh`, Debian 13) | `frontend/out/` (relatif au dépôt) | Kiosque Chromium X11 (`/kiosk` et/ou `/cinema`) + navigateur distant pour l'admin |
| **Windows Desktop** | Windows 10/11 (`.exe` Inno Setup) | `%ProgramFiles%\Bobine\frontend\out\` | Navigateur web par défaut au lancement + icône de notification en barre des tâches (systray). Supporte le mode Pupitre Studio (double écran) ou Headless (clamshell). |
| **macOS Desktop** | macOS Apple Silicon (`.dmg` / `Bobine.app`) | `Bobine.app/Contents/Resources/frontend/out/` | Navigateur web par défaut + menu bar companion. Supporte le mode Pupitre Studio ou Clamshell capot fermé. |
| **Linux Desktop** | Debian/Ubuntu/Mint (`.deb` / `apt.bobine.fit`) | `/usr/lib/bobine/frontend/out/` | Navigateur web par défaut + systray XDG. Supporte le mode Pupitre Studio ou Clamshell capot fermé. |
| **Tablette Android** | Tablettes ARM64 (`.apk`, Chaquopy) | Assets embarqués `pyStage/backend/frontend_out/` | Double WebView matérielle : tactile local (`/grid` ou accueil) + affichage externe HDMI (`/cinema`) |

Sur le profil Android, les données sont réparties sur **deux racines de stockage** distinctes (`backend/app/config.py::_android_internal_root()`) — la base SQLite, les miniatures, les logs, le branding et les pochettes radio vivent sur le stockage **interne** de l'app (`context.filesDir`, f2fs natif) tandis que les médias (vidéos, fonds, audio, radio) restent sur le stockage **externe** (`context.getExternalFilesDir`, servi par FUSE, visible depuis un gestionnaire de fichiers). Une installation existante est migrée automatiquement et sans risque de perte (copie, jamais de déplacement destructif, vérification `PRAGMA integrity_check` avant utilisation) au premier démarrage qui suit une mise à jour — cf. `android/app/src/main/python/bobine_bootstrap.py`.
| **Assistant GUI** | Linux x86_64 (`bobine-assistant`, Tauri 2 / Rust) | `assistant/ui/` (intégré au binaire Rust) | Fenêtre native GTK WebKit pour la découverte mDNS, scan LAN et déploiement SSH |

---

## 11. Licence

Bobine est distribué sous licence **GNU AGPL-3.0** (voir [`LICENSE`](../LICENSE) à la racine). Toute mise à disposition du logiciel, y compris via un service accessible en réseau, impose de publier le code source correspondant (y compris vos modifications) sous la même licence.

