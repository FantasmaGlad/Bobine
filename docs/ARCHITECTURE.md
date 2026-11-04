# Bobine : architecture

[English](ARCHITECTURE.en.md)

Référence courte pour comprendre et modifier Bobine. Le code fait foi.

## 1. Vue d'ensemble

- **Backend** : Python 3.11+, FastAPI et Uvicorn en **un seul processus**, SQLite (SQLAlchemy), APScheduler, ffmpeg. L'état de lecture vit en mémoire et part en WebSocket, sans bus externe.
- **Frontend** : Next.js en export statique, servi par le backend sur la même origine ; React, TypeScript, CSS à jetons (15 thèmes testés en contraste).
- **Android et Android TV** : Kotlin et CPython embarqué (Chaquopy) ; le backend tourne dans l'application.
- **Natif** : `projector/` (fenêtre de projection), `media/` et `devices/` (composants Rust), `assistant/` (installateur graphique Tauri).

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

**Configuration** : variables `BOBINE_*`, puis `/etc/bobine/config.toml`, puis `config.toml` du dépôt.

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

## 9. Licence

GNU AGPL-3.0 (voir [`LICENSE`](../LICENSE)).
