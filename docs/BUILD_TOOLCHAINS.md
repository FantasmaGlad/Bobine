# Build toolchains and release channels

The product version lives in `VERSION`. Stable, Beta and Canary use the same build
toolchains and dependency constraints; their branding, embedded channel and package
version differ. The npm and Cargo crate versions are separate technical versions.

## Versioned inputs

| Area | Input | Validation |
| --- | --- | --- |
| Web interface | Node 22, `frontend/package-lock.json`, `npm ci` | TypeScript, tests, static production export |
| Desktop/headless Python | Python 3.12 for packages; syntax and backend tests on 3.11, 3.12 and 3.13 | `backend/requirements.txt` with `constraints-desktop.txt`, `pip check`, complete pytest suite |
| Python tooling | `backend/requirements-test.txt`, `backend/requirements-build.txt` | Versioned test and PyInstaller dependencies, installed dependency reports in CI |
| Android | JDK 17, Gradle 9.7.1 with distribution SHA-256, AGP 9.2.1, Chaquopy 17.0.0 | SDK preparation, signed APKs and AABs, ABI and APK alignment checks |
| Android SDK/NDK | `android/toolchain.json`: compileSdk 37 (plateforme android-37.0), targetSdk 36, build tools 37.0.0, NDK r28c | Official archive size/checksum, ZIP CRC, extracted revision and executable LLVM tools |
| Android Python | Mobile 3.13, TV 3.11; exact pip requirements in `android/app/build.gradle.kts` | Both flavors build; separate FastAPI 0.99.1/Pydantic 1.10.26 compatibility tests on both Python versions |
| Native components | `rust-toolchain.toml` (1.99.1), each `Cargo.lock`, `cargo --locked` | Clippy and tests on target runners; media license gate; Android ELF architecture and 16 KiB alignment |
| Windows FFmpeg | `packaging/windows/ffmpeg.lock.json` | Immutable archive, SHA-256, PE architecture and actual FFmpeg/FFprobe startup on x64 and ARM64 |
| Workflow actions | Full commit references with readable release comments in CI and Play workflows | Workflow lint and real runner execution |

The Android SDK helper targets Linux build hosts, including the CI and Play jobs.
It reuses an NDK only after validation. If acquisition is needed, it stages and
validates the official archive before replacing the installation. A partial old
installation is retained for diagnosis. Only transient downloads or corrupt
archives receive bounded retries; permanent HTTP or disk errors fail the build.
All four Android signing secrets are required together. A pull request without
any signing secrets can run the remaining checks, but cannot qualify signed
artifacts. Partial signing configuration always fails.

Bundle verification uses strict JAR signature checks: self-signed upload
certificates may have no public CA chain, but added unsigned entries, modified
signed entries and duplicate ZIP paths fail validation. This proves signature
coverage, not a trust decision for an arbitrary third-party certificate.

The pinned AGP/Chaquopy combination is retained because it is inside Chaquopy's
published compatibility range. Gradle 10 and a Pydantic v2 migration for Android
are separate changes. Pydantic v1 configuration and desktop TestClient deprecation
warnings remain visible. OpenAPI GET/HEAD operation IDs and broadcasts submitted
during loop shutdown have dedicated regression checks.

## Native version order

For one base version, every package manager must order Canary before Beta, and
Beta before Stable. Build numbers also increase numerically within a channel.

| Product build | Debian Version | RPM Version-Release | Arch pkgver-pkgrel |
| --- | --- | --- | --- |
| Canary build 42 | `5.0.7~0.canary.42` | `5.0.7-0.1.canary.42` | `5.0.7alpha.42-1` |
| Beta build 7 | `5.0.7~1.beta.7` | `5.0.7-0.2.beta.7` | `5.0.7beta.7-1` |
| Stable | `5.0.7` | `5.0.7-1` | `5.0.7-1` |

The registry `backend/app/release_channel.py` derives these formats. Older
`5.0.5+canal.N` versions remain readable. The new base 5.0.6 is necessary for
migration from those already published packages: changing only the 5.0.5 suffix
would produce an older Debian version. `scripts/ci/test-package-versions.py`
checks actual dpkg, RPM and libalpm comparators, including 9-to-10 build increments,
Canary-to-Beta, Beta-to-Stable and migration from old 5.0.5 formats.

Rolling release tags stay `canary` and `beta`; download filenames stay fixed per
channel. A Stable tag must match `VERSION` and contain no iteration suffix.
Manual publication inputs are mutually exclusive. Play additionally checks that
the requested Stable version matches the selected source checkout; selecting an
old source still uses the SDK and version-validation tools from the workflow's
own revision. Preparing 5.0.7 on main does not change the last published Stable.

## Updating and qualifying the toolchains

1. Check the official compatibility matrices before changing AGP, Gradle,
   Chaquopy, Java, Rust or Python. Update immutable checksums together with URLs.
2. Resolve Python dependencies in isolated virtual environments, update the
   constraints, and run all supported Python jobs. Keep the Android v1 profile
   separate from the desktop v2 constraints.
3. Run `python3 -m unittest discover -s scripts/ci -p 'test_*.py'`, the backend
   suite, TypeScript and frontend build, native component checks and workflow lint.
4. Qualify the complete CI on the candidate revision: native Windows x64/ARM64,
   Linux amd64/arm64 packages, macOS package, signed mobile/TV APKs and bundles,
   package inspections, signatures and installation smoke tests. ARM64 component
   failures and bundle build failures block promotion.
5. Run the Play workflow against the intended source with release attachment
   disabled when only validating artifacts. Check store permissions and both
   bundled ABI sets. Publishing to the store is a separate explicit operation.

CI compilation, containers and x86_64 Android emulator startup do not establish
physical-device validation. Headless Wyse, Android ARM/TV, Windows and macOS
hardware acceptance remains necessary for release promotion. The current macOS
workflow builds for its runner architecture; it does not prove Intel hardware
compatibility. Linux containers and system packages follow their distribution
repositories, so these pins do not claim bit-for-bit reproducible installers.

Build success is separate from security acceptance. The Android Pydantic v1
profile retains legacy FastAPI/Starlette dependencies with published advisories;
GTK-related glib 0.18.5 also remains in the Linux GUI dependency graphs. These
findings require a separate compatibility and exposure assessment before Stable
promotion. Pinning these versions does not resolve their security advisories.
