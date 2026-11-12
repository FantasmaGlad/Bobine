# Bobine : architecture

[English](ARCHITECTURE.en.md)

Référence courte pour comprendre et modifier Bobine. Le code fait foi.

## 1. Vue d'ensemble

- **Backend** : Python 3.11+, FastAPI et Uvicorn en **un seul processus**, SQLite (SQLAlchemy), APScheduler, ffmpeg. L'état de lecture vit en mémoire et part en WebSocket, sans bus externe.
- **Frontend** : Next.js en export statique, servi par le backend sur la même origine ; React, TypeScript, CSS à jetons (9 thèmes en clair et en sombre, générés depuis une palette unique et testés en contraste).
- **Android et Android TV** : Kotlin et CPython embarqué (Chaquopy) ; le backend tourne dans l'application.
- **Natif** : `projector/` (fenêtre de projection), `media/` et `devices/` (composants Rust). L'installation à distance par SSH est un projet séparé : [Bobine Deploy](https://github.com/FantasmaGlad/bobine-deploy), qui pilote `install.sh --progress=json`.

```
navigateurs, TV, tablettes ──HTTP / WebSocket──> backend FastAPI (mono-processus) ──> SQLite
```

## 2. Démarrage local

```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001          # API de développement
cd frontend && npm install && npm run dev          # http://localhost:3000, appelle :8001
```

Validation avant contribution : `pytest` dans `backend/`, `npm test` et `npx tsc --noEmit` dans `frontend/`, `cargo test` dans les composants Rust touchés.

**Port** : 1903 par défaut (`BOBINE_PORT` ou `config.toml`). S'il est pris, Bobine essaie les 10 suivants puis un port du système ; `BOBINE_PORT_STRICT=1` interdit ce repli. Le port réel est écrit dans `backend-runtime.json`, à la racine des données.

**Configuration** : variables `BOBINE_*`, puis un seul fichier global (`%ProgramData%\Bobine\config.toml` sous Windows, `~/Library/Application Support/Bobine/config.toml` sous macOS, `$XDG_CONFIG_HOME/bobine/config.toml` s'il existe puis `/etc/bobine/config.toml` sous Linux), puis `config.toml` du dépôt.

## 3. Données

Une base SQLite (`data/database.db`) : vidéos, chapitres, sous-titres, playlists, cours audio, radio, planning, réglages, journaux et métriques. Les migrations sont de petites fonctions idempotentes de `backend/app/database.py`. Les médias d'origine ne sont jamais modifiés.

### 3.1 Profil Android : compatibilité Pydantic v1 et surveillance de dossiers

- Android utilise Pydantic 1.10 (pas de `pydantic-core` pour Chaquopy), les autres profils Pydantic 2 : le code passe par `app/utils/_pydantic_compat.py`, et `backend/tests/test_pydantic_v1_compat.py` refuse les constructions propres à la v2.
- La surveillance des dossiers d'import utilise `watchdog`, et un balayage périodique sur Android.

## 4. Diffusion

- Deux canaux vidéo indépendants : **câblé** (écran branché à la machine) et **réseau** (autres appareils), plus deux sorties radio. Un écran choisit son canal par `?channel=cable|network`.
- La position de lecture vient d'une **horloge serveur** diffusée en WebSocket ; chaque écran s'y aligne par un léger ajustement de vitesse, sans saut.
- La sortie HDMI est détectée sur chaque plateforme et ouvre `/cinema` en plein écran.

## 5. Modules

- **Import** : file unique, accélération matérielle selon la plateforme, téléversement par morceaux reprenable.
- **Radio** : bibliothèque, playlists, annonces, égaliseur par sortie.
- **Coach audio et ambiances** : cours audio sur fond visuel.
- **Périphériques et stockage** : audio, Bluetooth, Wi-Fi, clés USB et cartes SD, montées en lecture seule par défaut. Bobine fonctionne sur un réseau local de confiance : ces pages sont ouvertes à tous ses appareils.

## 6. Profils et installation

| Profil | Paquet | Particularités |
|---|---|---|
| Android, Android TV | APK | service de premier plan, base sur le stockage interne |
| Linux bureau | `.deb`, `.rpm`, pacman | barre système, service utilisateur |
| Appliance (mini PC) | `install.sh` | Debian 13, services `systemd`, kiosque Chromium |
| Windows | `.exe` | barre système |
| macOS | `.dmg` Apple Silicon | application et agent de lancement |

Appliance : `curl -fsSL https://bobine.fit/install.sh | bash` (options : `sudo ./install.sh --help`).

## 7. Mises à jour et publication

- Trois canaux : **Stable** (tag `Vx.y.z`), **Bêta** et **Canary** (tags mobiles, Canary à chaque commit sur `main`). `VERSION` est la seule source du numéro.
- La mise à jour intégrée vérifie l'empreinte SHA-256 avant d'installer ; sur Android et macOS elle reste manuelle.
- Chaque release publie `SHA256SUMS` et sa signature `SHA256SUMS.asc` : `gpg --verify SHA256SUMS.asc SHA256SUMS && sha256sum -c --ignore-missing SHA256SUMS`.
- Les dépôts Linux signés (APT, DNF, pacman) sont servis par `packages.bobine.fit`.

## 8. API

- REST sous `/api` (vidéos, playlists, planning, lecture, radio, imports, réglages, mises à jour, périphériques, stockage, santé). Schéma : `/openapi.json`.
- WebSocket `/ws/playback` : état de chaque canal avec son horloge, synchronisation du temps, changements de bibliothèque et de périphériques.
- Lecture par REST : `POST /api/playback/{canal}/{action}` et `POST /api/radio/{sortie}/{action}`, mêmes commandes que le WebSocket ; refus typés (409, 404, 422, 503).
- Configuration en fichiers JSON rangés par famille (`settings.json`, `machine.json`, `outputs/`, `library/`, `playlists/`, `schedule/`, `radio/`, `manifest.json`) : `GET /api/config/export`, `POST /api/config/apply` (essai à blanc par défaut, tout ou rien) ; copie lisible dans le dossier `config/` des données. Chaque objet porte un `uid` stable : un nom, un titre ou un fichier se modifie sans perdre l'objet, et `"prune": true` supprime ce qui a disparu d'un fichier de playlists ou d'étiquettes.
- Diagnostic : `GET /api/diagnostics/system` (constats `{code, severity, message, remedy}`) ; journaux : `GET /api/logs` (`source`, `level`, `since`, `limit`, horodatages UTC).
- Commande `bobine`, sur les mêmes routes, en local ou avec `--host` : `bobine status`, `bobine diagnose`, `bobine logs --level warning`, `bobine playback cable pause`, `bobine config export <dossier>`, `bobine config apply <dossier> --yes`. Lecture de l'état : `bobine library list|get`, `playlists`, `schedule list|next|get`, `devices status|audio|bluetooth|wifi|topology`, `storage status|volumes|portable|browse`, `metrics dashboard|system|history`, `imports list|cancel|diagnose`, `display get|set`, `playback <canal> status`, `radio <sortie> status`. Toute route de l'API a sa commande : `bobine media list --kind video` donne les identifiants, `bobine play video <id> --channel cable` lance la lecture. Référence complète, générée depuis le code : `docs/reference/` et [bobine.fit/fr/commandes](https://bobine.fit/fr/commandes). Les rapports d'écran (position, fin de média) restent réservés au WebSocket de l'écran qui joue, par conception. `--json` pour une sortie lisible par machine ; codes de sortie : 0 succès, 1 problème, 2 usage ou valeur invalide, 3 injoignable, 4 refus dû à l'état, 5 introuvable. Windows : `bobine.exe`, dans le `PATH`.

## 9. Licence

GNU AGPL-3.0 (voir [`LICENSE`](../LICENSE)).
