# Bobine 5.0.3 — Canary optimization batch

[Français](performance-5.0.3.md)

This batch targets the **Canary update channel**. The latest Stable release remains **5.0.2**. Successful CI builds do not replace device testing; the hardware checks below are still required before promotion to Stable.

## Changes

- **Linux and macOS packages**: strip debug symbols during PyInstaller packaging. On macOS, stripping takes place before bundle signing.
- **Radio libraries, playlists and audio courses**: load SQL relationships in batches to remove repeated queries per item from the affected lists and details.
- **Local network clients**: gzip JSON/text API responses and frontend text assets. Audio/video streams, Range/HEAD requests, downloads, WebSockets and loopback clients are excluded. Static variants retain distinct cache validators.
- **Android**: ARM-only distribution builds (`arm64-v8a` for mobile; `armeabi-v7a` and `arm64-v8a` for TV). x86_64 emulator development remains available with `./gradlew assembleMobileDebug -PbobineEmulator=true`, or `assembleTvDebug`. This option disables release/Play variants.
- **Bundled dependencies**: exclude YAML, watchfiles and Alembic/Mako tooling from desktop packages; remove Alembic/Mako from Android. Desktop builds retain `python-dotenv` because `pydantic-settings` imports it. Bobine's SQLite migrations remain part of the server.

## Development measurements

These measurements were taken on a Linux development workstation. They do not describe tablet or Wyse appliance performance.

| Measurement | Before | After | Scope |
|---|---:|---:|---|
| 5,000-track radio list: SQL queries | 5,001 | 11 | Relationship batches of 500 |
| Same list: median duration | 498 ms | 72 ms | October 20 measurement, local ORM access; excludes HTTP transfer |
| 5,000-track JSON over the network | 1,042,914 bytes | 30,519 bytes | LAN client accepting gzip |
| Frontend text over the network | 2.75 MB | 0.77 MB | 140 files, LAN client accepting gzip |
| Linux PyInstaller directory: debug symbols | 106 MB | 77 MB | Previous comparative Python 3.14 build; savings depend on bundled libraries |

**Android, comparing the same code and frontend**, first with the original configuration (x86_64 and Alembic), then with this batch:

| Signed APK | Before | After | Reduction |
|---|---:|---:|---:|
| Mobile | 53,714,687 bytes | 45,583,102 bytes | 15.1% |
| TV | 75,352,819 bytes | 67,342,873 bytes | 10.6% |

Additional October 20 comparison, using **the same sources, frontend and Python 3.14 environment**, with `strip=True` in both builds: dependency exclusions reduce the Linux directory from **78,552,616 to 77,154,928 bytes** and its gzip level 6 archive from **42,289,614 to 41,572,518 bytes**. This gain is separate from stripping debug symbols; these are not CI `.deb` sizes.

Compression cost on Wyse, memory during real use and final CI package sizes still need to be measured. Rust prototype figures are not counted as improvements in this version.

## Local validation

- Backend suite: **512 passing tests**, followed by **1 additional passing test** after making the `bobine-devices` binary available in the isolated checkout. The latter checks its protocol, without validating Windows/macOS devices.
- Frontend: **101 passing tests**, successful TypeScript check and production build.
- Firefox 158, Linux headless: **17/17 checks**, including MP4/MKV imports, HEVC adaptation, playback and upload resumption after a network interruption.
- Rebuilt Linux package: startup and successful health, settings, interface and radio list responses; video Range `206` without compression; gzip JSON and static assets checked through an isolated network interface.
- Android: rebuilt mobile/TV release APKs with verified signatures; four AABs (mobile/TV, release/Play) built without x86_64; emulator debug APKs checked for x86_64 and embedded Python. Requesting a release build with the emulator option is rejected. None of these artifacts was installed on a device during this validation.
- Python syntax checked for 3.11 compatibility. CI tests the backend on Python 3.11, 3.12 and 3.13.

Workstation Python and library versions may differ from CI package versions. Existing Pydantic deprecation warnings and an unawaited coroutine warning remain in the suite; this batch does not address them.

## Conditions before Stable

| Profile | Checks still required |
|---|---|
| Android mobile | Signed installation/update, cold start, import, playback, WebView and HDMI output |
| Android TV ARM 32-bit | Installation, import, playback, remote control and data preservation |
| Linux desktop amd64/arm64 | Install CI `.deb`, launch, import, playback and update |
| Wyse appliance | Continuous playback, imports, output synchronization and gzip cost measurements |
| Windows x64/ARM64 | Installation, packaged application startup, import, playback and update |
| macOS | Bundle signature after stripping, startup, import, playback and update |

Canary publication waits for backend tests, frontend, Firefox, installer checks and required package builds. CI results are available in [GitHub Actions](https://github.com/FantasmaGlad/Bobine/actions/workflows/ci.yml). The [Canary channel](https://github.com/FantasmaGlad/Bobine/releases/tag/canary) keeps its single moving tag.
