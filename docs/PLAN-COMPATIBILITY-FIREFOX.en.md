<p align="center">
  <img src="../Assets/Images/firefox.svg" alt="Firefox logo" width="96" />
</p>

# Implementation plan — Full support for Firefox / Gecko browsers

> English summary of [`PLAN-COMPATIBILITE-FIREFOX.md`](PLAN-COMPATIBILITE-FIREFOX.md) (the French document is the reference, with all tables and raw numbers).
> **Status (4.0.3)**: work packages **F0, F1, F2, F3, F5, F7, F8 delivered**; **F4 and F6 partly delivered** (see the table below). The reported import slowdown is still **not reproduced**: the root cause is not established.
> Firefox is a trademark of the Mozilla Foundation; its logo is used only to state compatibility, with no affiliation or endorsement.

## 1. Summary

1. **The reported import crash/lag could not be reproduced** on Firefox 157 (Linux, headless) — not locally, not through a 32 Mbit/s throttled link, not with 31 files / 1.5 GB, not with backend and browser limited to 2 CPU cores. **The root cause is therefore not established**; this plan does not guess it. It provides a diagnostic protocol (§4) and hardening that removes the plausible causes (§5).
2. Every Web API and protocol Bobine uses is **present** in Firefox 157 (WebSocket, XHR upload, Range, Web Audio, Gamepad, Wake Lock, `requestVideoFrameCallback`, `webkitdirectory`…).
3. Three **real defects** were proven: `HEAD` on media streams returns HTML; the drag-and-drop MIME filter (`File.type.startsWith("video/")`) is too strict (to be confirmed per OS); the library keeps HEVC/VP9/4K60 as-is (playable or not depending on the browser's OS and hardware).

## 2. Scope

Firefox desktop (Windows, macOS, Linux) and Firefox for Android: current release, previous release and current ESR. Derivatives (LibreWolf, Waterfox, Floorp, Zen): best effort. Tor Browser: "Standard" level only. Firefox for iOS uses WebKit and is treated like Safari. Rule: feature detection only, never `navigator.userAgent`; the Chromium kiosk of the headless appliance is unchanged.

## 3. Key measurements (Firefox 157, Linux, headless, no GPU)

| Scenario | Result |
|---|---|
| 2 files (10 MB + 190 MB), localhost | done in ~2 s; event-loop lag max 3 ms |
| 31 files (1.5 GB), 3 parallel transfers | done in ~14 s; lag max 28 ms; Firefox RSS 1.5 → 1.1 GB |
| 3 × 190 MB through 32 Mbit/s + 30 ms | ~61 s; lag max 4 ms; API latency max 20 ms |
| Backend + Firefox pinned to 2 cores, 3 × High10 import | < 4 s; API latency max 10 ms |
| Playback H.264 720p/1080p (up to 60 Mbit/s) | 0 dropped frames |
| Playback HEVC Main10 4K60 | 42/472 dropped (9 %) in the first isolated run; 0–2 in two later runs; a 185/477 drop with a 1.5 s main-thread stall was seen once while ffmpeg saturated the CPU |

Protocols: WebSocket ✅, `Range` 206 incl. suffix ranges ✅, CORS ✅, **`HEAD /stream` ❌ (returns `text/html`)**. AC-3/E-AC-3 are unsupported by Firefox (already re-encoded to AAC on import). HEVC/AV1 support depends on OS and hardware.
To verify on the bench (documented, not yet measured): `wakeLock` and `getGamepads` require a secure context, so they are expected to be absent on `http://<lan-ip>`.

## 4. Diagnostic protocol for the reported symptom

Collect for **one** crash: Firefox version/OS (`about:support`), whether the backend runs on the same machine as the browser, file sizes/extensions/codecs, whether the lag is during **transfer**, **processing** or **library display**, console + network tab, `about:crashes`, `about:memory`, the same files in Chrome/Edge, and server CPU (`ffmpeg`) during the lag.
Open hypotheses (none proven): H1 single multi-GB multipart request; H2 backend and browser on one weak machine with `ffmpeg -threads 0` at `nice 0`; H3 software 4K/HEVC decoding in the library preview; H4 React state update on every `progress` event × N transfers; H5 6-connections-per-host limit; H6 browser extensions.

## 5. Work packages

**Delivery status (4.0.3)** — F0 Firefox end-to-end bench (17 checks, CI job `firefox-smoke`): delivered; F1 HTTP conformance of streams (`HEAD`, `Range`, `If-Range`, `416`, JSON 404 under `/api/*`): delivered; F2 extension-based drop filter, throttled progress, adaptive concurrency, **resumable chunked upload** (resume verified after a real network cut), lowered `ffmpeg` priority on shared machines: delivered; F3 web rendition (H.264 8-bit ≤ 1080p), `?accept=` negotiation, library badge/button: delivered (produced on demand; automatic production is an opt-in setting); F4: partly (visibility resync, AudioContext keep-alive; hidden-tab sync over 30 min not measured); F5 *Settings → Browser compatibility*: delivered; F6: partly (`packaging/firefox/policies.json` kiosk policy; **optional local HTTPS not implemented**, policy file untested on a real Firefox, LibreWolf/Tor not tested); F7 `browserslist` + `eslint-plugin-compat`: delivered; F8 docs: delivered. Not measured: Windows, macOS, Firefox for Android, Firefox ESR.

| Lot | Goal | Acceptance |
|---|---|---|
| **F0** Gecko test bench | Promote [`scripts/browser-bench/`](../scripts/browser-bench/README.md) to a reproducible CI job (Firefox ESR + stable; Windows/macOS/Linux/Android); measure the "to verify" items | CI fails on JS error or event-loop lag > 200 ms during the reference import |
| **F1** HTTP conformance of media streams | `HEAD` on every `/stream`, correct `Content-Type`, `If-Range`, `416`, `ETag`; no `/api/*` path ever falls back to HTML | `curl -I` returns `video/mp4`; pytest GET/HEAD/Range/suffix/416 |
| **F2** Robust, frugal import | Extension/`ffprobe`-based drop filter with explicit errors; progress outside global React state (≤ 4 Hz); **resumable chunked upload** (8–16 MB); adaptive concurrency; lowered `ffmpeg` priority/thread cap on shared-machine profiles; free-disk check before accepting | 3 × 4 GB import: Firefox RSS < 1.5 GB, lag < 100 ms; 20 s network cut → resume; API latency < 250 ms during a 4K re-encode on 2 cores |
| **F3** "Plays everywhere" profile | Check profile/pix_fmt/level/frame rate; background **web rendition** (H.264 High ≤ 4.2, 8-bit 4:2:0, AAC) for third-party devices; client negotiation via `MediaCapabilities`; library badge | HEVC Main10 4K60/High10/VP9 play with < 1 % dropped frames on a non-accelerated Firefox; originals untouched |
| **F4** Third-party players (`/radio`, `/kiosk`, `/cinema`) | Unified, persisted autoplay-unlock gesture; `AudioContext` resume; clock followers independent of throttled timers in hidden tabs; graceful fallback without Wake Lock/Gamepad on insecure origins; `requestVideoFrameCallback` with fallback | `/radio` on Firefox starts on first click and stays within ±300 ms after 30 min hidden, no console errors |
| **F5** Hardware acceleration + built-in diagnostics | *Settings → Browser compatibility* page (MediaCapabilities, dropped frames, per-OS tips: VA-API on Linux, D3D11/HEVC extension on Windows, VideoToolbox on macOS, MediaCodec on Android); "Copy report" (no telemetry) | Report renders on Chromium, Firefox, Safari |
| **F6** Firefox derivatives & privacy | No logic based on fine `performance.now()`/canvas/`MediaCapabilities`; optional local HTTPS (local CA) for Wake Lock/Gamepad; optional Firefox kiosk `policies.json` | `/radio` and `/library` work on LibreWolf (default) and Tor Browser "Standard" |
| **F7** Tooling guarantees | `browserslist` (Firefox ESR, last 2 Firefox), `eslint-plugin-compat`, Stylelint unsupported-feature rule, `@supports` fallbacks | Build fails on unsupported features without fallback |
| **F8** Docs & non-regression | README (badge + section + logo), ARCHITECTURE §10.3, release notes, `AGENTS.md` rule, trademark notice | Docs FR/EN up to date; bench in the release checklist |

## 6. Limits of the study

One platform measured (Firefox 157, Linux, headless, no GPU); Windows, macOS and Firefox for Android **not measured**; synthetic media; no quantified Chrome comparison yet (planned in F0). Any import fix must be validated with the §4 protocol before being declared resolved.
