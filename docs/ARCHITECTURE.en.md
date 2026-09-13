# Bobine — Technical Architecture & Developer Reference

> **Bilingual document**: this file must be kept in sync with its French version ([`ARCHITECTURE.md`](ARCHITECTURE.md)) — last synchronized: 2026-09-13.

> Technical reference. For a user-oriented presentation (what Bobine is for, guided installation, getting started), see the **[README](../README.md)** (`README.fr.md` for French).

Playback, scheduling and control of class videos in a gym, on a dedicated mini PC. Single-process FastAPI server + SQLite, Chromium X11 kiosk, Next.js admin interface and mobile remote control.

This document is written for anyone who wants to **understand, operate, modify or deploy** the Bobine system: it describes the architecture as it actually stands (not an intention), the network contract, the data model, and the operating configuration on a dedicated mini PC.

---

## Table of Contents

1. [Stack & Getting Started](#1-stack--getting-started)
2. [General Architecture](#2-general-architecture)
3. [Data Model & SQLite Persistence](#3-data-model--sqlite-persistence)
3bis. [Import Pipeline, Multi-OS Hardware Acceleration & Reactive Cancellation](#3bis-import-pipeline-multi-os-hardware-acceleration--reactive-cancellation)
3ter. [Universal Multi-OS Hardware Telemetry & Attendance Metrics](#3ter-universal-multi-os-hardware-telemetry--attendance-metrics)
4. [Broadcast Channels & Playback Manager](#4-broadcast-channels--playback-manager)
5. [Radio Module](#5-radio-module)
6. [Audio Coach Mode & Animated Backgrounds](#6-audio-coach-mode--animated-backgrounds)
7. [Install Script & systemd Services](#7-install-script--systemd-services)
8. [HTTP API & WebSocket Reference](#8-http-api--websocket-reference)
9. [Operations & Network Discovery (Wyse)](#9-operations--network-discovery-wyse)
10. [Interface Matrix & Multi-Platform Compatibility](#10-interface-matrix--multi-platform-compatibility)
11. [License](#11-license)

---

## 1. Stack & Getting Started

### Technical Stack

- **Backend**: Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/) + `uvicorn` (single-process, see §2), [SQLAlchemy](https://www.sqlalchemy.org/), SQLite (`data/database.db`), `APScheduler` (scheduling), `watchdog` (import folder monitoring), `ffmpeg` with **multi-OS hardware acceleration** (`h264_mediacodec` on Android, `h264_videotoolbox` on macOS Apple Silicon/Intel, `h264_vaapi` on Linux with Intel QuickSync or AMD Mesa drivers, `h264_qsv` on Windows with an Intel QuickSync driver, universal fallback to `libx264`), Web Audio API (radio crossfade, browser-side). Strict policy of preserving 2K/4K streams in full, with no downsampling.
- **Frontend**: [Next.js](https://nextjs.org/) 16 (App Router, static export served by the backend in production), React 19, TypeScript, vanilla CSS (global styles + design tokens, **16 hot-swappable color themes** via `:root[data-theme=…]`, including the mineral "Charbon" / "Charbon Sombre" pair (light and dark, both WCAG AA/AAA certified), PWA (`manifest.json`), WebSockets, native HTML5 drag-and-drop, Web Audio API.
- **Operations & Kiosk**: Debian 13 (Trixie), Chromium in kiosk mode (X11 / `xinit`), `systemd` (backend, kiosk, audio guard and watchdog services), `avahi-daemon` (mDNS discovery).
- **Android Portability (`android/`)**: native Android application (Kotlin + embedded CPython via [Chaquopy](https://chaquopy.com/)), `minSdk 34` / `targetSdk 36` (Android 14-16, API 36 / Xiaomi Pad 8). Hardware dual-display via `DisplayManager` and `Presentation` (touch screen on `/grid` with no sidebar, external HDMI output via a USB-C dock on `/cinema` with a "Waiting for a class" idle screen), persistent `ForegroundService`, ARM64 NDK r28c binaries (native Bionic `ffmpeg`/`ffprobe`, 16 KB page size) with `av1_mediacodec` hardware decoding and ultra-fast `h264_mediacodec` encoding.
- **Installation & tooling**: `install.sh` (idempotent **Bash**: dynamic hardware detection, APT remediation, `--as-user`, machine-readable `--progress=json` output, §7); **graphical installation assistant** (`assistant/`, a **Tauri / Rust** desktop app, `/24` scan of every local network interface and SSH orchestration — see [`assistant/README.md`](../assistant/README.md)).

**Repository languages**: **Python** (FastAPI backend), **TypeScript/React** (Next.js frontend), **Kotlin** (Android app), **Bash** (`install.sh`), **Rust** (core of the installation assistant). **Continuous Integration** (GitHub Actions, `.github/workflows/ci.yml`) on every push/PR: frontend build, backend syntax check, assistant `cargo clippy` + `cargo test`, Android APK build and signing, and `install.sh` sanity checks (syntax + step-counter consistency).

### Local Development

**Prerequisites**: Node.js ≥ 20, Python ≥ 3.11.

```bash
# 1. Backend (FastAPI) — port 8001 in dev (see note below)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 2. Frontend (Next.js)
cd frontend
npm install
npm run dev             # available at http://localhost:3000
```

> **Dev quirk (port)**: served by `next dev` on `:3000`, the frontend routes its API/WebSocket calls to `localhost:8001` (see `getApiUrl`/`getWsUrl`) — hence the backend running on **8001** in development. An alternative without this offset, useful for checking the real rendering: `cd frontend && npm run build` (static export into `frontend/out`) then run the backend on `:8000` — it serves `frontend/out` itself at `/` (same origin as `/api`), so you can simply browse to `http://localhost:8000/<route>/`.

**Quick validation before committing**:

```bash
# Python syntax check (AST)
backend/.venv/bin/python -c "import ast; ast.parse(open('backend/app/main.py').read())"

# Frontend type check (TypeScript)
cd frontend && npx tsc --noEmit

# Installation assistant core tests (Rust) — same checks as CI
cd assistant && cargo test --workspace
```

### Configuration (`config.toml`)

Configuration is loaded in the following priority order:
1. Environment variables prefixed `BOBINE_` (highest priority).
2. `/etc/bobine/config.toml` (production, written by `install.sh`).
3. `config.toml` at the repository root (development).

| Key | Default | Role |
|---|---|---|
| `database.database_url` | `sqlite:///data/database.db` | SQLite connection URL |
| `media.media_dir` | `data/videos` | Storage for imported videos |
| `media.watch_dir` | `data/watched` | Folder watched for automatic import |
| `server.host` / `port` | `0.0.0.0:8000` | Backend HTTP listen address |
| `playback.wait_time_between_courses` | `0` | Inter-course delay (s) |
| `playback.volume_default` | `100` | Default volume (0-100) |

> **Upload temp files**: on startup the backend forces `tempfile.tempdir` to `data/tmp` (next to the media), instead of `/tmp`. On the Wyse, `/tmp` is an in-RAM tmpfs (~3.8 GB) that a large video/audio import would saturate (`OSError: No space left on device`, surfaced client-side as "There was an error parsing the body") even though the media disk has dozens of GB free.

---

## 2. General Architecture

```
┌─────────────┐      HTTP / WebSockets      ┌─────────────────────────────────┐
│  Frontend   │ ───────────────────────────►│        Backend FastAPI          │
│  Next.js    │                             │    (uvicorn, single-process)    │
│ (Kiosk /    │◀─────────────────────────── │  app/routers/* → playback_mgr   │
│  Admin /    │                             └─────────────────────────────────┘
│ Mobile Remote)│                                    │
└─────────────┘                                    │
                                                   ▼
                                          ┌──────────────┐
                                          │    SQLite    │
                                          │ (database.db)│
                                          └──────────────┘
```

The backend runs as a single `uvicorn` process (`--workers 1`). Playback state (position, playlist, schedule) lives directly in this process's memory and is broadcast to connected clients over WebSocket; no external state bus is needed to stay in sync.

> **History (before moving to a single process)**: the backend used to run with 4 `uvicorn` workers under the same master process, and Redis served as a shared state bus (playback position, tick locks, schedule synchronization) and an inter-worker Pub/Sub channel — since each worker ran its own copy of the `lifespan` and the `AsyncIOScheduler`, any side-effecting action (radio auto-start, triggering a schedule) had to be protected by a distributed lock so it would only happen once. Moving to a single process removes this entire class of problems by construction: there is now only one copy of each piece of state, and no more race between workers to arbitrate.

### Backend Layout (`backend/app/`)

- `main.py`: FastAPI application entry point, route initialization, startup events (`boot_state.py`) and the static asset server.
- `playback_manager.py`: Multi-channel (cabled/network) playback engine (`PLAYING`, `PAUSED`, `IDLE` state management, timing and resume).
- `radio_manager.py`: Playback engine for the Radio channel (§5) — state INDEPENDENT from `playback_manager.py` (track playlist, not video/course), same WebSocket connection.
- `scheduler_manager.py`: `APScheduler`-based manager for time-based scheduling (recurrences, conflict detection, offsets, radio windows).
- `models.py`: SQLAlchemy ORM declarations.
- `config.py`: Dynamic configuration manager.
- `routers/`: HTTP endpoints grouped by domain (`videos`, `backgrounds`, `playlists`, `audio`, `audio_playlists`, `schedule`, `playback`, `settings`, `logs`, `import_jobs`, `radio`, `radio_playlists`, `radio_announcements`).

---

## 3. Data Model & SQLite Persistence

The data schema is managed by **SQLAlchemy**. There is **no active Alembic** in this project (the `alembic/versions/` folder does not exist: only `alembic.ini`, `alembic/env.py` and `alembic/README` are present): tables are created by `Base.metadata.create_all()` at startup, and adding columns to existing tables goes through idempotent micro-migrations in `database.py::_migrate_add_missing_columns`. Storage is a single SQLite file (`data/database.db`).

### Main Entities

- `videos` / `backgrounds`: Media metadata (duration, resolution, codec, description/synopsis, fps, bitrate, audio channels and audio codec, thumbnails generated into `data/thumbnails`).
- `playlists` & `playlist_items`: Ordered video course playlists.
- `audio_courses` & `audio_tracks`: Imported audio courses and their associated tracks.
- `audio_playlists` & `audio_playlist_items`: Mixed audio-coach editions with a visual background assigned per track.
- `schedules` & `schedule_overrides`: Recurring or one-off schedules, with occurrence-exception handling (cancellation, replacement).
- `playback_state`: Playback state persisted per channel (*Cabled* and *Network*), including the saved interrupted action for automatic resume.
- `playback_sessions`: Attendance/listening sessions per channel and launch type, watched duration, total duration and completion status (`completed = True` if progress ≥ 90%).
- `course_ratings`: 5-star satisfaction ratings (score 1 to 5) collected on the coach desk `/grid` or the big screen `/cinema`, with UTC timestamp and channel.
- `settings`: Key/value settings hot-editable from the admin interface.
- `activity_log`: Log of the system's functional and technical events.
- `radio_tracks`, `radio_tags`, `radio_playlists` & `radio_playlist_items`: Music library and playlists for the Radio module (§5) — a subsystem independent from video courses/audio coach.
- `radio_announcements` & `radio_announcement_rules`: Courtesy reminders (announcements) and their trigger rules.

---

## 3bis. Import Pipeline, Multi-OS Hardware Acceleration & Reactive Cancellation

Bobine has a unified media processing/ingestion pipeline covering 4 distinct import flows: **course videos** (`/api/videos/upload` or the `data/watched` folder), **animated backgrounds** (`/api/backgrounds/upload` or the `data/backgrounds_watched` folder), **audio coach courses** (`/api/audio/upload` or the `data/audio_watched` folder), and **radio tracks** (`/api/radio/upload` or the `data/radio_watched` folder).

### 1. Centralized Queue & Real-Time Telemetry (`import_jobs.py`)

Every import triggered by a web upload or by the file watcher (`watchdog` / `PollingObserver`) generates a single job tracked in `app/utils/import_jobs.py`:
- **Successive states**: `uploading` → `normalizing` (or `transcoding`) → `thumbnail` → `done` (or `error` / `cancelled`).
- **Continuous FFmpeg telemetry**: invoked with `-progress pipe:1 -nostats`. A dedicated background thread continuously consumes `stderr` to prevent any buffer deadlock. Progress extraction reads the conversion speed (`speed`, e.g. `4.2x`), the completion percentage (`progress_percent`) and the estimated remaining time (`eta_seconds`) live.
- **API inspection**: `GET /api/import-jobs` exposes the ordered list of active and recently finished jobs with detailed progress, for the admin interface's polling.

### 2. Full Multi-OS Hardware Acceleration (`video_utils.py`)

The normalization engine uses a full 3-tier automatic hardware-acceleration pipeline (Full Hardware direct-VRAM → Hybrid GPU → CPU fallback) adapted dynamically to the system profile (`get_deployment_profile()`) and the graphics silicon:
- **Linux Desktop & Wyse Appliance (Intel QuickSync / AMD VA-API)**: Tier 1 Full HW via automatic DRM render-node detection (`_find_vaapi_device()`), direct decoding into VA-API surfaces (`-hwaccel vaapi -hwaccel_output_format vaapi`), GPU formatting `scale_vaapi=format=nv12` and hardware `h264_vaapi` encoding. Processing stays 100% inside VRAM with no RAM-PCIe transit, cutting CPU load by more than 93% (eliminating the 30W spikes). If a stream isn't supported, automatic fallback to Tier 2 Hybrid (`-vf "format=nv12,hwupload"`).
- **Android (Qualcomm Snapdragon / MediaTek SoC)**: Proactive hardware decoding paced with `-operating_rate 1000 -c:v <codec>_mediacodec` (AV1, HEVC, VP9, H.264) and native hardware encoding `h264_mediacodec` (`-pix_fmt nv12 -b:v <bitrate>`). Speed observed on a Xiaomi Pad 8: **4.2x to 5.1x** real time.
- **macOS (Apple Silicon M1 to M4 & Intel)**: Direct hardware decoding `-hwaccel videotoolbox` and hardware encoding `h264_videotoolbox` (`-q:v 65 -pix_fmt yuv420p`), ultra-fast conversion without stressing the CPU cores.
- **Windows (Intel QuickSync)**: Hardware decoding `-hwaccel qsv -hwaccel_output_format qsv` and `h264_qsv` encoding (`-preset fast`).
- **Universal fallback (Tier 3)**: if hardware acceleration fails or is unavailable (e.g. a headless server with no GPU), transparent automatic fallback to `libx264 -preset veryfast` with no task interruption.
- **Tightened keyframe interval**: every normalized video (regardless of encoder) gets `-g 60` (`-keyint_min 60` on the software fallback), i.e. one keyframe roughly every 2s at 30 fps — this guarantees reliable fast-forward/rewind and prevents an admin seek to an off-keyframe position from leaving the decoder stuck (see §4, "Recovering from a stuck video decoder").

### 3. Golden Rule: Full Preservation of Source Quality (Zero Degradation)

Bobine strictly respects source media fidelity:
- **No destructive downsampling**: native 2K (1440p) and 4K (2160p) resolutions are never reduced to 1080p.
- **Adaptive high-fidelity target bitrates** (`_get_target_bitrate`):
  - **4K UHD (≥ 2160p)**: 28 Mbps (max bitrate 35 Mbps)
  - **2K QHD (≥ 1440p)**: 14 Mbps (max bitrate 18 Mbps)
  - **1080p FHD (≥ 1080p)**: 6 Mbps (max bitrate 8 Mbps)
  - **720p HD**: 3.5 Mbps (max bitrate 4.5 Mbps)

### 4. Reactive Cancellation & Atomic Cleanup

- **Immediate stop**: clicking the cross (✕) in the floating upload panel issues a `DELETE /api/import-jobs/{job_id}` call.
- **Process interruption**: `cancel_job()` flags the atomic cancellation, sends `SIGTERM` (then a safety `SIGKILL` after 1.5s) to the registered FFmpeg subprocess, and cancels the thread-pool `Future`.
- **Full purge**: the interruption raises `JobCancelledError`, causing immediate deletion of partial destination files (`dest_path`, temporary thumbnails) with no database write at all.
- **Preventive startup cleanup**: on launch, the backend scans the media directories to remove orphaned temporary leftovers from an abrupt power loss.

### 5. Pre-Start Duration Estimate & Queue (`encode_speed_stats.py`)

The FFmpeg telemetry from §1 (`progress_percent`, `eta_seconds`, `speed`) only exists once re-encoding has actually started — the preceding steps (queue wait, file analysis, copy) used to display only an "in progress" indicator with no duration. Two estimates now complete this telemetry:
- **Initial per-task estimate** (`estimated_seconds`): set as soon as file analysis finishes (before FFmpeg is launched), computed from the source video's duration divided by an average speed (`x` real time) historically observed for the current (hardware encoder, 4K/2K/1080p resolution tier) pair. This moving average is persisted in the `settings` table (key `encode_speed_stats:<encoder>:<tier>`) and refined after every successful re-encode; until a sample exists, a conservative default is used per encoder. Purely indicative, it is overwritten by `eta_seconds` as soon as real FFmpeg progress starts.
- **Cumulative queue estimate** (`queue_eta_seconds`): for a given task, the sum of the estimated remaining time (live ETA if already re-encoding, otherwise the initial estimate) of every unfinished task ahead of it, plus its own remaining time. Computed in `list_jobs()`, alongside `queue_position` — an estimate, not a guarantee.

Both fields are exposed by `GET /api/import-jobs` and displayed in the floating upload panel (`UploadManager.tsx`): `~X min (estimate)` during analysis/copy, then `(N ahead, ~X min total)` while a task waits its turn.

---

## 3ter. Universal Multi-OS Hardware Telemetry & Attendance Metrics

### 1. Universal Hardware Supervision (`hardware_info.py`)

Bobine embeds a low-level hardware introspection module (`backend/app/utils/hardware_info.py`) exposed by `GET /api/settings/system` and consumed by the Settings panel (`/settings`) and the dashboard (`/metrics`). To guarantee an accurate, professional presentation (no raw technical codes, no generic `aarch64` architecture strings or vague labels), the module resolves full commercial names and audits the real physical components across the 5 execution profiles:

- **Processor (CPU)**:
  - *Android ARM64*: reads the AOSP system properties `ro.soc.model` (e.g. `Snapdragon 8 Elite`, `Dimensity 9300`) and falls back to `ro.board.platform` or `/proc/cpuinfo`.
  - *Linux Desktop & Wyse Headless*: extracts the commercial model from `/proc/cpuinfo` (`model name`), regex-cleaning superfluous suffixes (`(R)`, `(TM)`, redundant frequencies).
  - *macOS Desktop*: calls `sysctl -n machdep.cpu.brand_string` (e.g. `Apple M3 Pro`, `Intel Core i7`).
  - *Windows Desktop*: direct query into the Windows Registry `HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0\ProcessorNameString` (very fast, no process spawn).
- **Graphics Chip (GPU)**:
  - *Android ARM64*: identifies the Adreno chip via the Qualcomm graphics driver's sysfs nodes `/sys/class/kgsl/kgsl-3d0/gpu_model` (e.g. `Qualcomm Adreno 825`), or Mali nodes for MediaTek SoCs.
  - *Linux Desktop & Wyse Headless*: walks the DRM sysfs tree `/sys/class/drm/card*/device/` and resolves the name via `udevadm` or `lspci` extraction (Intel UHD/Iris Xe, AMD Radeon Graphics, Nvidia GeForce) with empty-parentheses cleanup.
  - *macOS Desktop*: queries `system_profiler SPDisplaysDataType`.
  - *Windows Desktop*: non-blocking PowerShell query `Get-CimInstance Win32_VideoController` with a strict timeout (1.5s).
- **Memory (RAM)**:
  - Reports total and used capacity (in GB and %), plus manufacturer metadata: brand/maker (Samsung, Micron, SK Hynix, Crucial, Corsair), memory technology (LPDDR5X, LPDDR5, DDR5, DDR4, LPDDR4X) and maximum clock frequency (e.g. 8533 MT/s, 6400 MHz).
  - *Android*: diagnosed via `/proc/meminfo`, platform properties and memory sysfs.
  - *Linux / Wyse*: non-root SMBIOS inspection via `udevadm info -p /devices/virtual/dmi/id` or `dmidecode -t memory` if available.
  - *macOS*: `system_profiler SPMemoryDataType`.
  - *Windows*: WMI query `Win32_PhysicalMemory` (Manufacturer, SMBIOSMemoryType, Speed).
- **Primary Storage**:
  - Commercial identification of the system disk (e.g. `Samsung SSD 990 PRO 2TB`, `Western Digital WD Black SN850X`, `256 GB UFS 4.0 Flash Storage` on Android).
  - Total/free space and usage percentage via `shutil.disk_usage()` (or `StatFs` on Android).
  - *Linux / Wyse*: sysfs nodes `/sys/block/<disk>/device/model` and `lsblk`.
  - *Android*: inspects the eMMC / UFS bus type (`/sys/block/sda/device/model` or `mmcblk0`).
- **Electrical Power in Watts (W) & Cumulative Energy (Wh)**:
  - Live instantaneous measurement of overall power draw:
  - *Linux x86 / Wyse*: reads the Intel/AMD RAPL (Running Average Power Limit) interface under `/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` with 100 ms differential sampling.
  - *Laptops / Tablets / Macs on battery*: instantaneous `P = U * I` computation via battery sensors (sysfs `/sys/class/power_supply/`, `AppleSmartBattery` on macOS via `ioreg`).
  - *On mains power (battery maintained, AC charger)*:
    - On a Linux laptop: hardware APU/GPU/SoC sensors (`hwmon` `amdgpu` or RAPL) are prioritized over the `BAT1` battery probe (which would report a false 0.05 W leakage current once the battery is full).
    - On Android (Chaquopy): detects the plugged-in state (`plugged > 0` or `CHARGING`/`FULL` status). At a steady 100%, since the chemical current at the battery terminals is 0 µA, the real active power is computed from the SoC's thermal/energy profile and the instantaneous CPU load scaling (3.2W baseline + dynamic CPU scaling).
    - On macOS: detected via `ioreg -rc AppleSmartBattery` (direct `Watts` or `ExternalConnected`).
    - On Windows: queries AC state via `Get-CimInstance Win32_Battery`.
  - *Cumulative Energy & Average Power*: continuous trapezoidal integration of instantaneous power over time (`cumulative_energy_wh = ∫ P dt`), exposed in Watt-hours (Wh) alongside the average power (`average_power_watts`).
- **CPU and GPU Temperatures (°C)**:
  - Reads hardware thermal sensors under `/sys/class/thermal/thermal_zone*` and `/sys/class/hwmon/`.
  - On Android, specifically targets the CPU and Adreno GPU zones `/sys/class/kgsl/kgsl-3d0/temp`.
- **Uptime & Runtime**:
  - Operating-system uptime and Bobine server continuous runtime (since the FastAPI instance was initialized).

### 2. Attendance Metrics Engine, System Telemetry & Retention (`/metrics`)

- **Modular Interface Decoupling (`/metrics`)**:
  - The Metrics section is split into two distinct, ergonomic spaces:
    - **Courses & Attendance (`/metrics/courses`)**: session KPIs, completion rate, watch duration, 24h hourly attendance histogram and rankings of the most-watched and best-rated courses.
    - **System & Hardware (`/metrics/system`)**: live machine monitoring (CPU, RAM, Disk, CPU/GPU temperatures, electrical power in W, cumulative energy in Wh, server runtime and OS uptime).
  - **History Side Drawer (`TelemetryHistoryDrawer.tsx`)**:
    - Clicking any metric card directly opens an animated side drawer from the right with an interactive time-series chart (responsive SVG).
    - Quick time filters: **1 hour**, **6 hours**, **24 hours** and **7 days**.
    - Displays extremes (minimum, maximum, average) and a dynamic timestamp.
- **Dynamic, Extensible Database (`SystemMetricLog`)**:
  - SQLite table `system_metrics_logs` designed with an extensible EAV schema (`metric_type`, `value`, `unit`, `recorded_at`), accepting any future hardware probe (watts, cpu, ram, disk, temp_cpu, temp_gpu, etc.) without a heavy migration.
  - Automatic, non-blocking sampling orchestrated by `scheduler_manager.py`.
- **Configurable Retention & Automatic Purge (`logs_retention_days`)**:
  - Log and hardware-metric retention period configurable in Settings (`GET`/`PUT /api/settings`, field `logs_retention_days`, default: 7 days).
  - Periodic background task (`_cleanup_old_logs_and_metrics`) atomically purging records older than the configured threshold.
- **Session Collection (`playback_sessions`)**: tracks every video session played (course id, title, channel, manual/schedule trigger, watched duration, total duration, `completed` flag computed at ≥90%).
- **Satisfaction Ratings (`course_ratings`)**: collects 1-to-5-star feedback after playback:
  - Contextual display: on the coach desk (`/grid`) inside the finished course's container in dual-screen mode; on the big screen (`/cinema` HDMI) in headless mode.
  - Smooth, continuous 5-minute (300s) auto-close countdown bar, synced to the system clock.
  - Full color harmonization: rating stars, gauges and the power icon (bolt and Watt unit) synced to the active theme's CSS variable (`var(--accent-primary)`).
- **Analytics Dashboard (`GET /api/metrics/dashboard`)**:
  - 4 key indicators (average satisfaction /5, completion rate %, total broadcast duration in hours, number of sessions).
  - 24-hour attendance histogram (pure CSS Grid, automatic peak-hour detection).
  - Ranking of the most-played and best-rated courses.

---

## 4. Broadcast Channels & Playback Manager

The system drives two **strictly independent** video broadcast channels, plus a 3rd music channel (§5):

1. **Cabled Channel (`channel=cable`)**: The main display channel wired to the mini PC's physical video output (room screen / kiosk).
2. **Network Channel (`channel=network`)**: A secondary channel for network broadcast or auxiliary screens.
3. **Radio Channel (`channel=radio`)**: A 3rd channel, fully independent from the first two (no interaction) — continuous music playback on a dedicated station. Managed by a separate state manager (`radio_manager.py`), not the `playback_manager` below.

Each screen displays `/kiosk` or `/cinema` depending on the output chosen by the admin (`/api/settings/display-output`, e.g. cable → `cinema`, network → `kiosk`). The cabled screen (`127.0.0.1`, detected via `isWiredDisplay()`) always follows its stored output. **The studio desk `/grid` exclusively drives the cabled channel (HDMI)**: there is no `/grid` interface for the network channel (which is driven from `/dashboard-network`). **Empty library**: `/cinema` shows a full-screen idle screen (big logo + clock + "No course available") instead of a black screen; `/kiosk` has its own idle screen (clock + next course). **Course categories** are **free-form** labels (no more fixed RPM/Sprint/The Trip): typed input with suggestions from already-used categories, dynamic filtering and grouping.

**Universal controls: physical remotes, keyboards, mice, touch and gamepads** (see the `useKioskRemote` hook & HTML5 Gamepad API): all broadcast and control surfaces (`/cinema`, `/grid`, `/kiosk`, `/radio`) react consistently to every input device:
- **USB & Bluetooth remotes**: presentation dongles, media remotes and "air remotes" recognized as standard HID keyboards.
- **Gamepads**: Xbox, PlayStation (DualShock / DualSense), 8BitDo, Nintendo Switch Pro controllers and generic USB/BT gamepads, natively supported via the standard **HTML5 Gamepad API** (`navigator.getGamepads()`). D-Pad and left analog stick for navigation, A/Cross to launch/confirm, B/Circle to go back, X/Y/Start for Play/Pause, L1/R1 for time skip and L2/R2 for volume.
- **Touch & Mouse**: direct card activation on click/tap, tap-to-wake playback controls, interactive pause button and scrub bar.
- **2D Spatial Navigation (`moveDomFocus2D`)**: continuous geometric computation in the viewport to move the card-selection cursor card by card (up, down, left, right) with a dynamic light halo (`.kiosk-remote-focus`).

### Resume After Interruption (Resilience Rule)

When an automatic schedule (`scheduler`) needs to start while a manual playback is in progress:
1. `playback_manager` interrupts the manual playback and saves the exact position and media id into `playback_state`.
2. The scheduled course runs.
3. At the end of the schedule, the interface automatically offers to **resume to the exact second** the interrupted course.

### Playback Recovery & Smoothness (`/kiosk`, `/cinema`)

On some hardware decoders (MediaCodec on Android, VA-API on Linux/Wyse), a hot seek to an off-keyframe position could leave the video pipeline out of sync or stuck on the last decoded frame while the audio track kept advancing. Several complementary, coordinated safeguards cover this case in `/kiosk` and `/cinema`:
1. **Protected seeks and pause/seeked sync**: every assignment of `currentTime` goes through `seekWhenReady()`. If the element is currently playing, it is temporarily paused to freeze the audio clock before the time jump, then resumed only once the `seeked` event fires (with a 1200 ms safety timeout). This guarantees the audio never gets ahead of the video GOP reconstruction.
2. **Anti-reentrancy guard**: forbids triggering a new seek while `el.seeking` is active, preventing perpetual overwriting of the decoder buffer.
3. **Post-seek grace period (3,500 ms)**: on mirror kiosks (network or multi-screen), periodic `position_tick` realignments are ignored for 3.5 seconds after a seek, to let buffers and display stabilize.
4. **Soft stall detection with no jitter**: aggressive watchdogs are replaced by a non-destructive check for prolonged freezes (> 7.5 consecutive seconds with no clock progress outside loading/seek), triggering a clean `.play()` relaunch with no jarring artificial pause/seek cycle.
5. **Debounce protection (1.5s) and monotonic time smoothing on `/grid`**: eliminates accidental double commands when launching a course, and displays a steady second-by-second playback time with no backward jump caused by network packet jitter.

### Gapless A/B Deck Video Engine (`/cinema`) & 5-Star Rating

- **A/B Deck Gapless Video Engine**: on Chromium and Android WebView, assigning a new `video.src` destroys the hardware decoding pipeline and produces a 200-600 ms black screen. Bobine now mounts **two permanent `<video>` elements in the DOM** (`deckARef` and `deckBRef`) inside a `.cinema-deck-container`. The Active Deck plays live (`opacity: 1`, `zIndex: 2`), while the next course or the idle screen is preloaded behind the scenes on the Standby Deck (`opacity: 0`, `zIndex: 1`, `preload="auto"`). As soon as `canplay` fires, a hardware CSS crossfade (`opacity 0.4s ease`) happens with zero flicker or black flash.
- **5-Star Rating System**: at the natural end of a course, or once 95% progress is crossed, the control widget on `/grid` (coach desk) or the cinematic end-of-course screen on `/cinema` (big screen) offers a touch/physical 5-star rating card (Google Icons `star` / `star_outline`). Controllable via media remote, gamepad, mouse or touch, with a 5-minute (300s) auto-close countdown. Ratings are persisted to SQLite (`course_ratings`).
- **Playback & Attendance Sessions**: every video broadcast is tracked in the `playback_sessions` table with the channel, trigger type, exact watched duration and the `completed` flag (true if ≥ 90% of the course was watched), feeding the `/metrics` dashboard.

---

## 5. Radio Module

A "Spotify-like" music subsystem **fully independent** from video courses/audio coach (dedicated `radio` channel, `radio_*` tables, `radio_manager.py` state manager) — library, playlists, continuous playback, crossfade and voice reminders.

- **Surfaces**: `/radio` (the dedicated station's screen — display + controls, opened manually in a browser, no systemd kiosk service), the admin "Radio" tab (remote control on `/radio-remote`), "Radio Audio Track" (library on `/radio-library`), "Reminders" (announcements on `/radio-announcements`), and a 3rd "Radio" tab on the Schedule page (`/schedule/?channel=radio`). Outside of playback (idle screen + "Start radio" overlay), the station displays a **full-screen big logo** (opaque theme background); unlocking the station **does not start any music** unless a radio is actually active (`idle` state), to avoid desyncing the admin interface.
- **Library**: import of every audio format (automatic transcoding of what the browser can't play), extracted (ID3) or manual cover art, browsing by artist/album/tags. The admin "Radio Audio Track" screen (`/radio-library`) is an **overview**: a filter sidebar (playlists / tags / genres / artists), a multi-select grid with bulk actions (tagging, adding to a playlist), editable tag chips, a drag-and-drop playlist editor.
- **Playback**: continuous, queue, shuffle, repeat (track/playlist), **crossfade** (Web Audio API — two `<audio>` elements routed through a `MediaElementAudioSourceNode → GainNode → destination` graph, fade started client-side ahead of server confirmation).
- **Reminders**: courtesy announcements with a description, trigger rules (every N tracks / every X minutes / at fixed times / manual), inserted either at the end of the current track or via an immediate fade ("duck" — reuses the same Web Audio graph as the crossfade). Every reminder is **loudness-normalized on import** (`ffmpeg loudnorm` EBU R128, 2 passes, -10 LUFS target) so it's heard at least as loud as the music. Dedicated admin screen (`/radio-announcements`): import, activation, rules, manual trigger.
- **24/7 & Scheduling**: a playlist marked as default (`is_default`) loops continuously; auto-start on boot (`radio_autostart_on_boot`). **With no default playlist, the fallback plays the entire library shuffled and looped** (a virtual "Whole Library" playlist, `playlist_id=None`, recomposed on every launch so it's always up to date with the library): the radio is never silent at startup without needing a playlist to be created; setting an `is_default` playlist reclaims priority. The Schedule feature can layer recurring time windows on top of this (24/7 option) that, at the end of the window, revert to the default ambiance — or, failing that, to this same library fallback rather than silence.
- **Config** (`radio_dir`, `radio_covers_dir`, `radio_announcements_dir`, `radio_watch_dir`, `radio_volume_default`, `radio_crossfade_seconds`, `radio_announcement_duck_level`, `radio_announcement_fade_ms`, `radio_autostart_on_boot`): see `config.py` — folders unified under `${REPO_DIR}/data` by `install.sh` like the rest of the media.

---

## 6. Audio Coach Mode & Animated Backgrounds Hub

**Audio Coach** mode broadcasts audio courses (voice tracks / rhythmic music) over the room's sound system while projecting a dynamic, cinematic visual ambiance on the cabled (HDMI) screen.

- **Coach Control Console (`/coach`)**: A reactive, touch-friendly studio control console.
  - **On a landscape tablet and computer (>= 900px)**: An ergonomic, asymmetric two-column layout.
    - *Left column*: Track info, interactive progress bar, rest/exercise timer, oversized touch transport controls, a reactive volume slider, loop/chain buttons, and an integrated dropdown playlist with direct track jumping.
    - *Right column*: A **16:9 Stage Monitor** (live video feed from the room's HDMI output showing video, cover art or a sober cinematic glow, with live title and progress overlay) sitting above a **16:9 touch ambiance palette** for switching the live projected visual ambiance in one tap with no audio interruption.
  - **On a smartphone and compact screen (< 900px)**: A streamlined single-pane interface with retractable touch drawers (*bottom sheets*) for quickly selecting tracks and visual ambiances.
- **Automatic redirect to the control console**: As soon as Coach mode is enabled on the kiosk, any navigation to the cabled dashboard (`/dashboard-cable`) instantly and automatically redirects to `/coach`, ensuring frictionless coordination for any staff member or coach working from a mobile device or remote station.
- **Visual Ambiances Hub (`/backgrounds`)**: A centralized space dedicated to managing 16:9 visual ambiance loops. Gone is the old, unintuitive switcher: every card offers a dynamic video preview on hover, live broadcast badges ("On Cable", "On Network", "Coach Default"), a full immersive modal player, one-click immediate broadcast buttons outside a session, and the ability to assign the default ambiance (`default_coach_background_id`).
- **Visual Audio Selector (`/audio`)**: Assigning an ambiance in the audio library is done via an interactive 16:9 card opening a visual selection gallery with thumbnails, replacing the old text menu.
- **Chain Timer (`audio_chain_timer_seconds`)**: Configurable transition delay between two audio tracks (editable from `/api/settings`).
- **Persistence & Fallback**: Persistence of the `default_coach_background_id` setting in the SQLite `settings` table. Any audio course with no specific background assigned automatically inherits the configured default ambiance.

---

## 7. Install Script & systemd Services

Production installation is done via the idempotent shell script `install.sh` on Debian 13 (Trixie).

```bash
# Full installation on the target machine
sudo ./install.sh
```

### Installation Options (`sudo ./install.sh --help`)

| Option | Description |
|---|---|
| `--no-kiosk` | Install the backend only (no Chromium X11 / audio) |
| `--dry-run` | Preview actions without making changes |
| `--check` | Diagnose an existing installation |
| `--skip-packages` | Update the project (after deploying code, §9) without reinstalling `apt` packages |
| `--skip-build` | Do not rebuild the Next.js frontend |
| `--as-user LOGIN` | Target account when the script runs as **root directly** (a Debian machine **without sudo**, launched via `su -`) — see below |
| `--channel=stable\|beta` | Update channel (default `stable`) — see "Update Channel" below |
| `--progress=json` | **Machine-readable** output: one JSON line per event (`run_begin` / `step` `start\|ok\|skip\|error` / `run_end`) on **fd 3**, used to drive a progress bar (graphical assistant). The human-readable log is unchanged — see "Graphical Installation Assistant" below |
| `--uninstall [--purge] [--purge-data]` | Progressive system uninstall |

**Dynamic hardware detection**: the installer no longer assumes an Intel GPU. It detects the GPU (`lspci`) and CPU (`lscpu`) and installs the matching packages — **Intel**: `intel-media-va-driver-non-free` (fallback `i965-va-driver`); **AMD/Ryzen**: `mesa-va-drivers` + `firmware-amd-graphics`; **NVIDIA**: software decoding + a warning — plus **microcode** (`amd64-microcode`/`intel-microcode`) and Wi-Fi firmware if a wireless interface is present. Non-free packages requiring APT components that are absent (`non-free`, `non-free-firmware`, split since Debian 12) are handled by **enabling those components** as needed (a `.bobine.bak` backup of the sources).

**Audio**: `alsa-utils` (`amixer`/`aplay`/`alsactl`) and the `pipewire`/`pipewire-pulse`/`wireplumber`/`pulseaudio-utils` stack are installed systematically — without them, the WirePlumber configuration described below (automatic jack-plug switching, anti-whistle) and the `amixer`/`pactl` commands used by `kiosk-xinitrc`/`bobine-audio-mute.sh` would silently fail on a minimal (netinst) Debian. A **`capabilities`** step, at the end of installation (and replayable via `--check`), verifies that audio (`aplay -l`) and VA-API hardware decoding (`vainfo`, H.264 profile) actually work, rather than assuming the configuration was sufficient.

**System tuning** (the `tuning` step): CPU governor set to `performance` (`bobine-cpu-governor.service`, since the machine stays plugged into mains power continuously) and the systemd journal capped at 200 MB (`/etc/systemd/journald.conf.d/bobine.conf`) — screen sleep (X11 DPMS/screensaver) has already been disabled in `kiosk-xinitrc` since an earlier version.

**Privileges — two paths**: either `sudo ./install.sh` from a normal account (the script refuses to run as root with no target account); or, on a minimal Debian **with no sudo** (a root password set at install time, non-sudoer user), as **root directly** via `su - -c "\$PWD/install.sh --as-user <login> -y"`. The script then installs `sudo` and writes the restricted sudoers rule, so that the admin's "Sync" / "Uninstall" buttons work afterward. Commands run "as the user" (venv, pip, build) go through `sudo -u` if present, otherwise `runuser`.

### systemd Services Created

- `bobine-backend.service`: FastAPI Uvicorn API on port 8000 (single-process, `--workers 1`). `Restart=always`.
- `bobine-kiosk.service`: Full-screen Chromium kiosk mode on `xinit` (X11). `Restart=always`.
- `bobine-audio-guard.service`: AUDIO-only guard — a oneshot that mutes Master/Speaker/Headphone at boot and shutdown (silence outside the kiosk session), overridden by `kiosk-xinitrc` once it's ready. Watches nothing else.
- `bobine-watchdog.timer` + `bobine-watchdog.service`: HEALTH watchdog. The timer triggers `scripts/watchdog.sh` (`OnBootSec=90s`, then every 30s) which polls `GET /api/health` and **automatically restarts a dead component**: if `/api/health` doesn't respond 200 → restarts `bobine-backend`; if the kiosk service is enabled but no Chromium process exists → restarts `bobine-kiosk`. Complements `Restart=always` (which handles *process* death) for *logical* failures (backend alive but database locked, Chromium frozen, etc.).
- `bobine-redirect.service`: nftables redirect from port 80 to 8000.
- `bobine-cpu-governor.service`: a oneshot that sets the CPU governor to `performance` on every boot (the installer's `tuning` step).

**Health check** — `GET /api/health` returns `{"status": "ok"|"degraded", "components": {"database", "kiosk"}}`, with HTTP `200` if the database responds, `503` otherwise (the kiosk's state is indicative and doesn't affect the HTTP status code). This is the endpoint consumed by the watchdog above and by any external monitoring.

No dedicated service for the Radio channel (decision A5, see §5): `/radio` is opened manually in a browser, on the same backend.

### Graphical Installation Assistant

A standalone graphical application (`assistant/`, built with **Tauri 2 / Rust**) runs on the **administrator's machine** (Windows, macOS or Linux), locates the mini PC on the LAN (a `/24` scan of every local network interface), connects to it over SSH, audits the hardware, then **drives `install.sh`** with a progress bar and a live view of the installation logs. `install.sh` remains the **single source of truth** — the assistant **orchestrates** it, it doesn't reimplement anything. Full details and build instructions: [`assistant/README.md`](../assistant/README.md).

The network scan shows **every** device that responds (not just Bobine targets) — hostname, IP, OS hint, open ports — so that a user preparing a headless deployment can recognize their kiosk among the rest of the network. SSH authentication accepts, in addition to a password, a private key explicitly imported via a native file picker (`tauri-plugin-dialog`).

### Update Channel (Stable / Beta)

Two channels, chosen at install time (`install.sh --channel=stable|beta`, or in the Tauri assistant's wizard) and changeable at any time from Settings → Updates ("Bobine Beta Program"):

- **Stable** (default): `GET /api/updates/check` queries `/repos/.../releases/latest` — this structurally excludes pre-releases on the GitHub API side, so this channel can never receive one, even in case of an application bug. Every stable version has its own `Vx.y.z` tag and its own GitHub Releases entry (normal history).
- **Beta**: queries `/repos/.../releases/tags/beta` — a **single, mobile** tag, republished in place on every release rather than a new tag per iteration (`beta.1`, `beta.2`, … would eventually have made the Releases page unreadable). Update detection compares the installed **commit** against the commit targeted by this tag (`target_commitish`) — there is no version number that advances with every build on this channel. An equal or newer stable version always supersedes the beta being followed.

The choice is persisted (the `update_channel` setting in the database for the backend; `/etc/bobine/update-channel` for `install.sh`) and also drives the headless profile's `apply_update()` (the "Update" button): `git checkout <tag>` rather than `git pull --ff-only`, which allows a genuine rollback (downgrade) to an earlier tag — and correctly follows a mobile tag (`git fetch --tags --force`).

On the publishing side (`.github/workflows/ci.yml`): the `version` job computes both the version number (single source of truth: the `VERSION` file at the repository root) and the **channel**, structurally separate from there on:
- pushing a strict `Vx.y.z` tag → `release-stable` (a new GitHub Releases entry, `prerelease: false`, notes drawn from `docs/releases/<TAG>.md`, which must exist);
- a direct push to `main` (outside of a tag), or a manual trigger (`workflow_dispatch`, the *publish_beta* checkbox, from any ref — useful for republishing with no new commit) → `release-beta` (force-moves the `beta` tag onto the current commit, deletes then republishes the single Beta release, with auto-generated notes — a changelog since the last stable tag). The Beta thus follows `main` continuously, never falling behind.

Beta artifact filenames are **fixed** (`Bobine-Setup-beta.exe`, `Bobine-beta.dmg`, `bobine_beta_amd64.deb`) — never a version number or a `~` character in them (GitHub Releases silently rewrites `~` to `.` in downloaded asset names). The *internal* version number (shown in the app, the `Version:` field of the Debian package) stays precise: `VERSION`/`COMMIT` are bundled into every package (the same PyInstaller `datas` as `config.toml`) and read at runtime by `app.utils.version` — including on packaged profiles (Windows/macOS/Linux desktop), which have no `.git` to consult otherwise.

### Restricted sudo Authorization & Uninstall from the Interface

`install.sh` writes `/etc/sudoers.d/bobine`, authorizing **without a password, and only**, two actions triggered from the admin:

- **restarting** the services (`systemctl restart`) — the "Sync Screens" button (Settings → Maintenance): every connected screen **clears its browser cache** then reloads (re-downloading the new assets), and the backend + kiosk are restarted. Used after a media update or when something is stuck;
- the **uninstall** wrapper `/usr/local/sbin/bobine-uninstall` — the "Uninstall" button (Settings → **Danger Zone**). The wrapper detaches the reset via `systemd-run` (to survive the backend service stopping) then runs `install.sh --uninstall --purge --purge-data -y`: stops/removes the services + `/etc` config + the app + the venv + **all data** (shared `apt` packages are kept). The UI requires retyping the phrase "UNINSTALL"; outside an installed machine (a dev workstation), the endpoint refuses cleanly.

---

## 8. HTTP API & WebSocket Reference

### HTTP Endpoints (`/api`)

| Domain | Prefix | Description |
|---|---|---|
| **Videos** | `/api/videos` | Import, listing, detail, normalization, deletion and distinct categories (`/videos/programs`) |
| **Video Playlists** | `/api/playlists` | Video playlist management (CRUD, replay) |
| **Animated Backgrounds** | `/api/backgrounds` | Management of the visual loop library |
| **Audio Coach** | `/api/audio` | Audio course import (MP3/ZIP), track management |
| **Audio Playlists** | `/api/audio-playlists` | Mixed audio-coach playlists with backgrounds |
| **Schedule** | `/api/schedule` | Schedulers, occurrences and exceptions |
| **Playback** | `/api/playback` | Playback control (play, pause, seek, stop, resume) |
| **Settings** | `/api/settings` | Dynamic configuration (playback/theme/language/`deployment_profile`/`update_channel`), video output, storage space (`/settings/storage`), screen sync (`POST /settings/system/reset` — clears caches + reload + restarts services), universal ZIP backup & restore (`/settings/system/backup`, `/settings/system/restore`), and factory reset or machine uninstall (`POST /settings/system/reset-data`, `POST /settings/system/uninstall`, confirmation phrase required) |
| **Updates** | `/api/updates` | `GET /updates/check` — queries GitHub Releases according to the current channel (Stable/Beta, see §7) and deployment profile for the matching asset; `POST /updates/apply` — triggers `git checkout <tag>` + restart (headless profile only, 400 otherwise) |
| **Imports** | `/api/import-jobs` | Import task queue (`GET /api/import-jobs` with percentage, ETA in seconds and speed) and reactive cancellation (`DELETE /api/import-jobs/{id}` with FFmpeg stop and purge) |
| **Logs** | `/api/logs` | Viewing and downloading system logs |
| **Radio — Library** | `/api/radio` | Tracks (CRUD, artists/albums/tags), radio playlists, channel state (`/api/radio/state`) |
| **Radio — Reminders** | `/api/radio/announcements`, `/api/radio/announcement-rules` | Announcements (import + description), trigger rules, manual trigger |
| **Metrics & Attendance** | `/api/metrics` | Club-wide analytics (`GET /metrics/dashboard` with period/channel filters, satisfaction/completion/24h attendance KPIs, course ranking and hardware telemetry) and 5-star ratings (`POST /metrics/ratings`, `GET /metrics/ratings`) |

### WebSockets

- `/ws/playback`: Real-time broadcast of playback state per channel — cabled, network **and radio** (`channel=radio`, same connection, `radio_*` command vocabulary specific to the music channel) — *position*, *duration*, *current media*, inter-course countdown. Also broadcasts `library_change` (a video import/modification/deletion — upload, watched folder, or title edit): `/grid`, `/cinema` and `/library` reload their list without waiting for their periodic poll.

---

## 9. Operations & Network Discovery (Wyse)

On the local network, the production Wyse machine (`bobine-prod.local` / Dell Wyse 5070) gets its IP address via **DHCP**.

### Network Discovery Protocol (If the IP Changes)

1. **Test the current address or the mDNS name** (the IP below is a documentation example — replace it with the site's real address):
   ```bash
   curl -s --connect-timeout 2 http://192.0.2.10:8000/api/settings
   curl -s --connect-timeout 2 http://bobine-prod.local:8000/api/settings
   ```
2. **Automatic Nmap subnet scan** (if the IP isn't reachable):
   ```bash
   SUBNET=$(ip route | grep default | awk '{print $3}' | cut -d. -f1-3).0/24
   nmap -p 8000 --open "$SUBNET" -oG - | grep "8000/open"
   ```

### Remote Operations Commands (SSH)

```bash
# Check the status of the systemd services on the Wyse
ssh fanta@<WYSE_IP> "systemctl status bobine-backend bobine-kiosk"
```

### Deploying to the Wyse

**Warning: `git pull` does NOT work on the Wyse**: its network blocks GitHub entirely (both ports 22 and 443 to github.com). The `/home/fanta/Bobine` repository on the Wyse **is not a git clone** — deployment is done by copying (`rsync`) from a dev machine on the same local network, never by `git pull` on the target machine itself.

```bash
# 1. From the dev machine, on the same LAN as the Wyse — always with
#    --dry-run first, to check that no "deleting" line touches data/:
rsync -a --delete --dry-run \
  --exclude='.git/' --exclude='data/' --exclude='backend/data/' --exclude='backend/.venv/' \
  --exclude='frontend/node_modules/' --exclude='frontend/.next/' --exclude='frontend/out/' \
  --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.db*' --exclude='*.log' \
  --exclude='backend/.pytest_cache/' --exclude='VideoTest/' \
  --exclude='.claude/' --exclude='.agents/' --exclude='.gemini/' \
  --exclude='AGENTS.md' --exclude='CLAUDE.md' \
  ./ fanta@<WYSE_IP>:/home/fanta/Bobine/
# (then without --dry-run once verified)

# 2. On the Wyse: if the deployment adds/changes media folders, config.toml
#    settings, or systemd services, rerun the installer
#    (idempotent, never touches data/ outside --uninstall --purge-data):
ssh fanta@<WYSE_IP> "cd /home/fanta/Bobine && sudo ./install.sh --skip-packages -y"
# For a CODE-ONLY change (no new folder/setting/service),
# a simple rebuild is enough instead of the step above:
#   ssh fanta@<WYSE_IP> "cd /home/fanta/Bobine/frontend && npm run build"

# 3. install.sh does NOT restart an already-active service: restart explicitly
#    to load the new code (these two commands are NOPASSWD):
ssh fanta@<WYSE_IP> "sudo -n systemctl restart bobine-backend.service && sudo -n systemctl restart bobine-kiosk.service"

# 4. Verify: API health, active services, data/ disk space unchanged
ssh fanta@<WYSE_IP> "curl -s localhost:8000/api/health; systemctl is-active bobine-backend bobine-kiosk; du -sh /home/fanta/Bobine/data"
```

Commits stay local until a machine with GitHub access (outside the Wyse's LAN) pushes them to `origin/main` — deployment never depends on that push.

---

## 10. Interface Matrix & Multi-Platform Compatibility

Bobine is built on a **single, unified frontend interface** built with Next.js 16 (App Router) and statically exported (`npm run build` → `frontend/out`). This interface is shared and embedded identically across **every deployment profile**.

### 10.1 Map of the Interface's 20 Routes (+ `/` redirecting to `/dashboard-cable`)

| Category | Route(s) | Description & Multi-OS Specifics |
|---|---|---|
| **Broadcast & Kiosk** | `/kiosk` | Automatic full-screen kiosk (scheduling, inter-course, instant start with no delay). Clock with `suppressHydrationWarning` and network sync (`/api/time`). |
| | `/cinema` | An "Apple TV"-style selection showcase with a hero, category rows, HID remote support and the **Gapless A/B Deck Video Engine** (dual decoder, no black screen). In dual-screen Studio Desk mode (`dual_screen`), the external screen shows a passive *"Waiting for a course"* idle screen while selection happens on the `/grid` touch console; in Headless mode (`headless`), the external screen shows the full interactive grid directly. 5-star rating on the end screen. |
| | `/grid` | A dedicated touch selection/control interface (Android tablets, laptops in Studio Desk mode). **Exclusively drives the cabled channel (HDMI)** (no network equivalent, administered via `/dashboard-network`). Supports touch, mouse, HID remote and gamepad navigation with debounce and monotonic time smoothing. Touch 5-star rating at the end of the course. (see [`docs/cahier-des-charges-affichage-hybride.md`](cahier-des-charges-affichage-hybride.md)). |
| **Control & Dashboards** | `/dashboard-cable`<br>`/dashboard-network` | Independent control dashboards for the Cabled and Network channels (direct trigger, resume, volume, one-click ambiance broadcast). Automatic, transparent redirect from `/dashboard-cable` to `/coach` when Coach mode is active. |
| **Coach Control Console** | `/coach` | Responsive studio control console: two columns on a landscape tablet and desktop with an oversized touch player, timer, integrated dropdown playlist, a **16:9 Stage Monitor** (live HDMI feed from the room) and a **16:9 touch ambiance palette** with a live 1-tap switch. Compact single-pane version with touch drawers on mobile. |
| **Administration** | `/settings` | Configuration manager: 16 themes (including the mineral "Charbon" / "Charbon Sombre" pair, light and dark, WCAG AA/AAA certified), cabled display mode selector (dual-screen Studio Desk vs Headless), dynamic network refresh (15s polling + manual button), full monitoring (CPU, GPU, RAM, Storage, Power in W, Temperatures, Uptime), ZIP backup/restore. |
| | `/metrics`<br>`/metrics/courses`<br>`/metrics/system` | Analytics and attendance dashboard (Beta since 3.0.5): 4 key indicators (average 5★ satisfaction, ≥90% completion rate, broadcast volume in hours, number of sessions), a pure-CSS 24h hourly attendance histogram, ranking of favorite courses, real-time hardware telemetry, an EAV database and a history drawer (1h, 6h, 24h, 7d). |
| | `/library` | Video library with metadata, duration and universal custom thumbnail upload (`PUT /api/videos/{id}/thumbnail` via Pillow, no ffmpeg dependency). |
| | `/backgrounds` | Visual Ambiances Hub (Beta since 3.0.5): centralized management of 16:9 ambiance loops with hover video previews, direct broadcast to the Cabled and Network outputs, an immersive modal player and default-background configuration for coach courses. |
| | `/audio`<br>`/audio-playlists` | Audio-coach library and playlist manager with a modal 16:9 visual ambiance selector and dynamic assignment. |
| | `/playlists`<br>`/schedule`<br>`/logs` | Management of ordered lists, recurring time-based scheduling (APScheduler) and system log inspection. |
| **Radio Channel** | `/radio`<br>`/radio-announcements`<br>`/radio-library`<br>`/radio-remote` | Independent continuous audio channel with Web Audio API music chaining, automatic ducking and courtesy voice reminders. |

---

### 10.2 Mounting & Integration per Deployment Profile

The FastAPI server (`backend/app/main.py`) dynamically mounts the static folder depending on the running profile, via the `RevalidateStaticFiles` class (injecting `Cache-Control: no-cache` to force ETag revalidation and avoid any heuristic HTTP-cache freeze):

| Profile | Target & Format | Frontend Location Served | Main UI Consumer |
|---|---|---|---|
| **Headless Appliance** | Dell Wyse / Mini PC (`install.sh`, Debian 13) | `frontend/out/` (relative to the repository) | Chromium X11 kiosk (`/kiosk` and/or `/cinema`) + a remote browser for admin |
| **Windows Desktop** | Windows 10/11 (`.exe` Inno Setup) | `%ProgramFiles%\Bobine\frontend\out\` | Default web browser on launch + a taskbar notification icon (systray). Supports Studio Desk mode (dual screen) or Headless (clamshell). |
| **macOS Desktop** | macOS Apple Silicon (`.dmg` / `Bobine.app`) | `Bobine.app/Contents/Resources/frontend/out/` | Default web browser + a menu bar companion. Supports Studio Desk mode or closed-lid Clamshell. |
| **Linux Desktop** | Debian/Ubuntu/Mint (`.deb` / `apt.bobine.fit`) | `/usr/lib/bobine/frontend/out/` | Default web browser + XDG systray. Supports Studio Desk mode or closed-lid Clamshell. |
| **Android Tablet** | ARM64 tablets (`.apk`, Chaquopy) | Embedded assets `pyStage/backend/frontend_out/` | Dual hardware WebView: local touch screen (`/grid` or home) + external HDMI display (`/cinema`) |

On the Android profile, data is split across **two storage roots** (`backend/app/config.py::_android_internal_root()`) — the SQLite database, thumbnails, logs, branding and radio cover art live on the app's **internal** storage (`context.filesDir`, native f2fs), while media (videos, backgrounds, audio, radio) stays on **external** storage (`context.getExternalFilesDir`, served over FUSE, visible from a file manager). An existing install is migrated automatically with no risk of data loss (copy, never a destructive move, with a `PRAGMA integrity_check` before use) on the first launch following an update — see `android/app/src/main/python/bobine_bootstrap.py`.
| **GUI Assistant** | Linux x86_64 (`bobine-assistant`, Tauri 2 / Rust) | `assistant/ui/` (bundled into the Rust binary) | Native GTK WebKit window for mDNS discovery, LAN scanning and SSH deployment |

---

## 11. License

Bobine is distributed under the **GNU AGPL-3.0** license (see [`LICENSE`](../LICENSE) at the repository root). Any way of making the software available, including via a network-accessible service, requires publishing the corresponding source code (including your modifications) under the same license.
