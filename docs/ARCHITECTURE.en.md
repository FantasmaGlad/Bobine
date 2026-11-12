# Bobine: architecture

[Français](ARCHITECTURE.md)

A short reference to understand and change Bobine. The code is authoritative.

## 1. Overview

- **Backend**: Python 3.11+, FastAPI and Uvicorn in a **single process**, SQLite (SQLAlchemy), APScheduler, ffmpeg. Playback state lives in memory and is sent over WebSocket, with no external bus.
- **Frontend**: Next.js static export, served by the backend on the same origin; React, TypeScript, token-based CSS (9 palettes, each in light and dark, generated from a single source and contrast-tested).
- **Android and Android TV**: Kotlin with embedded CPython (Chaquopy); the backend runs inside the app.
- **Native**: `projector/` (projection window), `media/` and `devices/` (Rust components). Remote installation over SSH is a separate project: [Bobine Deploy](https://github.com/FantasmaGlad/bobine-deploy), which drives `install.sh --progress=json`.

```
browsers, TVs, tablets ──HTTP / WebSocket──> FastAPI backend (single process) ──> SQLite
```

## 2. Local development

```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001          # development API
cd frontend && npm install && npm run dev          # http://localhost:3000, calls :8001
```

Before contributing: `pytest` in `backend/`, `npm test` and `npx tsc --noEmit` in `frontend/`, `cargo test` in the Rust components you touch.

**Port**: 1903 by default (`BOBINE_PORT` or `config.toml`). If it is taken, Bobine tries the next 10, then a system port; `BOBINE_PORT_STRICT=1` forbids this fallback. The actual port is written to `backend-runtime.json`, at the root of the data folder.

**Configuration**: `BOBINE_*` variables, then a single global file (`%ProgramData%\Bobine\config.toml` on Windows, `~/Library/Application Support/Bobine/config.toml` on macOS, `$XDG_CONFIG_HOME/bobine/config.toml` if present then `/etc/bobine/config.toml` on Linux), then the repository `config.toml`.

## 3. Data

One SQLite database (`data/database.db`): videos, chapters, subtitles, playlists, audio classes, radio, schedule, settings, logs and metrics. Migrations are small idempotent functions in `backend/app/database.py`. Original media files are never modified.

### 3.1 Android profile: Pydantic v1 compatibility and folder watching

- Android uses Pydantic 1.10 (no `pydantic-core` for Chaquopy), other profiles Pydantic 2: code goes through `app/utils/_pydantic_compat.py`, and `backend/tests/test_pydantic_v1_compat.py` rejects v2-only constructs.
- Import folders are watched with `watchdog`, and by periodic scanning on Android.

## 4. Playout

- Two independent video channels: **wired** (the screen plugged into the machine) and **network** (other devices), plus two radio outputs. A screen picks its channel with `?channel=cable|network`.
- The playback position comes from a **server clock** sent over WebSocket; each screen follows it with a slight speed adjustment, without jumps.
- The HDMI output is detected on every platform and opens `/cinema` full screen.

## 5. Modules

- **Import**: single queue, platform hardware acceleration, resumable chunked upload.
- **Radio**: library, playlists, announcements, per-output equalizer.
- **Audio coach and ambiences**: audio classes over a visual background.
- **Devices and storage**: audio, Bluetooth, Wi-Fi, USB drives and SD cards, mounted read-only by default. Bobine runs on a trusted local network: these pages are open to all its devices.

## 6. Profiles and installation

| Profile | Package | Notes |
|---|---|---|
| Android, Android TV | APK | foreground service, database on internal storage |
| Linux desktop | `.deb`, `.rpm`, pacman | tray icon, user service |
| Appliance (mini PC) | `install.sh` | Debian 13, `systemd` services, Chromium kiosk |
| Windows | `.exe` | tray icon |
| macOS | `.dmg` Apple Silicon | app and launch agent |

Appliance: `curl -fsSL https://bobine.fit/install.sh | bash` (options: `sudo ./install.sh --help`).

## 7. Updates and publishing

- Three channels: **Stable** (`Vx.y.z` tag), **Beta** and **Canary** (moving tags, Canary on every commit to `main`). `VERSION` is the only source of the version number.
- The built-in updater checks the SHA-256 digest before installing; on Android and macOS it stays manual.
- Every release publishes `SHA256SUMS` and its signature `SHA256SUMS.asc`: `gpg --verify SHA256SUMS.asc SHA256SUMS && sha256sum -c --ignore-missing SHA256SUMS`.
- Signed Linux repositories (APT, DNF, pacman) are served by `packages.bobine.fit`.

## 8. API

- REST under `/api` (videos, playlists, schedule, playback, radio, imports, settings, updates, devices, storage, health). Schema: `/openapi.json`.
- WebSocket `/ws/playback`: state of each channel with its clock, time synchronization, library and device changes.
- Playback over REST: `POST /api/playback/{channel}/{action}` and `POST /api/radio/{output}/{action}`, same commands as the WebSocket; typed refusals (409, 404, 422, 503).
- Configuration as JSON files grouped by family (`settings.json`, `machine.json`, `outputs/`, `library/`, `playlists/`, `schedule/`, `radio/`, `manifest.json`): `GET /api/config/export`, `POST /api/config/apply` (dry run by default, all or nothing); a readable copy lives in the `config/` data folder. Every object carries a stable `uid`: a name, title or file can change without losing the object, and `"prune": true` removes what disappeared from a playlists or tags file.
- Diagnostics: `GET /api/diagnostics/system` (findings `{code, severity, message, remedy}`); logs: `GET /api/logs` (`source`, `level`, `since`, `limit`, UTC timestamps).
- `bobine` command, on the same routes, locally or with `--host`: `bobine status`, `bobine diagnose`, `bobine logs --level warning`, `bobine playback cable pause`, `bobine config export <folder>`, `bobine config apply <folder> --yes`. Reading state: `bobine library list|get`, `playlists`, `schedule list|next|get`, `devices status|audio|bluetooth|wifi|topology`, `storage status|volumes|portable|browse`, `metrics dashboard|system|history`, `imports list|cancel|diagnose`, `display get|set`, `playback <channel> status`, `radio <output> status`. Every API route has its command: `bobine media list --kind video` gives the identifiers, `bobine play video <id> --channel cable` starts playback. Full reference, generated from the code: `docs/reference/` and [bobine.fit/en/commands](https://bobine.fit/en/commands). Screen reports (position, end of media) stay on the WebSocket of the playing screen, by design. `--json` for machine-readable output; exit codes: 0 success, 1 problem, 2 invalid usage or value, 3 unreachable, 4 refused by the current state, 5 not found. Windows: `bobine.exe`, on the `PATH`.

## 9. License

GNU AGPL-3.0 (see [`LICENSE`](../LICENSE)).
