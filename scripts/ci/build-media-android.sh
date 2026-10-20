#!/usr/bin/env bash
# Build an Android/Bionic executable, packaged as lib*.so for nativeLibraryDir.
# Keeps the release ABI policy: mobile ARM64; TV ARM64 + ARM32. x86_64 is opt-in
# for debug emulators only; Gradle already disables release for emulator builds.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to the Android NDK r28 or newer directory}"
API_LEVEL="${BOBINE_MEDIA_ANDROID_API:-34}"
EMULATOR="${BOBINE_MEDIA_ANDROID_EMULATOR:-0}"
if [[ ! "${API_LEVEL}" =~ ^[1-9][0-9]*$ ]] || (( API_LEVEL < 23 || API_LEVEL > 34 )); then
    echo "BOBINE_MEDIA_ANDROID_API must be 23..34 (application minSdk is 34)." >&2
    exit 2
fi
if [[ "${EMULATOR}" != 0 && "${EMULATOR}" != 1 ]]; then
    echo "BOBINE_MEDIA_ANDROID_EMULATOR must be 0 or 1." >&2
    exit 2
fi
for tool in cargo rustup python3; do
    command -v "${tool}" >/dev/null || { echo "Missing build tool: ${tool}" >&2; exit 1; }
done
python3 - "${ANDROID_NDK_HOME}/source.properties" <<'PY'
from pathlib import Path
import re
import sys
properties = Path(sys.argv[1])
if not properties.is_file():
    raise SystemExit('Missing NDK source.properties')
version = re.search(r'^Pkg.Revision\s*=\s*(\d+)', properties.read_text(), re.M)
if not version or int(version.group(1)) < 28:
    raise SystemExit('Android NDK r28 or newer is required')
PY
case "$(uname -s)" in
    Linux) HOST_TAG=linux-x86_64 ;;
    Darwin) HOST_TAG=darwin-x86_64 ;;
    *) echo "Build this Android component on a Linux or macOS NDK host." >&2; exit 2 ;;
esac
TOOLS="${ANDROID_NDK_HOME}/toolchains/llvm/prebuilt/${HOST_TAG}/bin"
for tool in llvm-strip llvm-readelf; do
    [[ -x "${TOOLS}/${tool}" ]] || { echo "Missing NDK tool: ${tool}" >&2; exit 1; }
done
# Absolute target dir makes output deterministic even if the caller configures
# a different Cargo target-dir for desktop builds.
TARGET_DIR="${REPO_DIR}/media/target/android"
for target in aarch64-linux-android armv7-linux-androideabi; do
    rustup target add "${target}"
done
if [[ "${EMULATOR}" == 1 ]]; then
    rustup target add x86_64-linux-android
fi

build_target() {
    local target="$1" abi="$2" clang_prefix="$3" cargo_key="$4"
    local linker="${TOOLS}/${clang_prefix}${API_LEVEL}-clang"
    [[ -x "${linker}" ]] || { echo "Missing NDK linker for ${target}/API ${API_LEVEL}." >&2; exit 1; }
    local flags='-C link-arg=-Wl,-z,max-page-size=16384 -C link-arg=-Wl,-z,common-page-size=16384'
    # Explicit flags keep Cargo's linker invocation independent of CMake/ndk-build
    # defaults. Validate the final ELF rather than assuming NDK version suffices.
    env -u RUSTFLAGS -u CARGO_ENCODED_RUSTFLAGS "CARGO_TARGET_${cargo_key}_LINKER=${linker}" \
        "CARGO_TARGET_${cargo_key}_RUSTFLAGS=${flags}" \
        CARGO_TARGET_DIR="${TARGET_DIR}" \
        cargo build --manifest-path "${REPO_DIR}/media/Cargo.toml" --release --locked --target "${target}"
    local output="${REPO_DIR}/android/app/src/main/jniLibs/${abi}/libbobine_media.so"
    mkdir -p "$(dirname "${output}")"
    "${TOOLS}/llvm-strip" --strip-unneeded -o "${output}" "${TARGET_DIR}/${target}/release/bobine-media"
    chmod 755 "${output}"
    python3 - "${TOOLS}/llvm-readelf" "${output}" "${abi}" <<'PY'
import subprocess
import sys
reader, binary, abi = sys.argv[1:]
headers = subprocess.check_output([reader, '-h', '-lW', '-d', binary], text=True)
expected_machine = 'AArch64' if abi == 'arm64-v8a' else ('ARM' if abi == 'armeabi-v7a' else 'X86-64')
machine = next((line.split(':', 1)[1].strip() for line in headers.splitlines() if 'Machine:' in line), '')
if expected_machine not in machine:
    raise SystemExit('Unexpected ELF architecture: ' + machine)
if not any('Type:' in line and 'DYN' in line for line in headers.splitlines()):
    raise SystemExit('The packaged component must be a PIE executable')
interpreter = '/system/bin/linker' if abi == 'armeabi-v7a' else '/system/bin/linker64'
if '[Requesting program interpreter: ' + interpreter + ']' not in headers:
    raise SystemExit('Expected the Android/Bionic dynamic linker')
loads = [line.split() for line in headers.splitlines() if line.strip().startswith('LOAD ')]
if not loads or any(int(line[-1], 16) < 16384 for line in loads):
    raise SystemExit('Packaged ELF LOAD segments are not 16 KiB aligned')
if 'libc.so.6' in headers or 'ld-linux' in headers:
    raise SystemExit('A glibc binary cannot be packaged for Android')
print(abi + ': Android PIE, 16 KiB ELF LOAD alignment, ' + str(__import__('os').path.getsize(binary)) + ' bytes')
PY
}

build_target aarch64-linux-android arm64-v8a aarch64-linux-android AARCH64_LINUX_ANDROID
build_target armv7-linux-androideabi armeabi-v7a armv7a-linux-androideabi ARMV7_LINUX_ANDROIDEABI
if [[ "${EMULATOR}" == 1 ]]; then
    build_target x86_64-linux-android x86_64 x86_64-linux-android X86_64_LINUX_ANDROID
fi
