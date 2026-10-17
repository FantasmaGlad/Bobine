#!/usr/bin/env bash
# Compile ffmpeg et ffprobe pour armeabi-v7a (Bionic, NDK) et les dépose dans
# jniLibs/armeabi-v7a sous les noms libffmpeg.so / libffprobe.so.
#
# Pourquoi compiler : le seul binaire arm64 publié par le dépôt tiers utilisé
# pour arm64-v8a n'a pas d'équivalent 32 bits, or beaucoup de boîtiers Android
# TV (Chromecast avec Google TV, Xiaomi TV Stick/Box) ont un système 32 bits et
# ne peuvent pas exécuter de binaire arm64. Ce ne sont pas de vraies
# bibliothèques : des exécutables renommés pour profiter du seul mécanisme de
# packaging natif d'Android (cf. packaging.jniLibs dans build.gradle.kts).
#
# Build LGPL (ni GPL ni non-free), même périmètre que le binaire arm64 :
# décodage/encodage matériel via MediaCodec, pas de libx264.
#
# Usage : ANDROID_NDK_HOME=/chemin/vers/ndk-r28c ./build_ffmpeg_armv7.sh
set -euo pipefail

FFMPEG_VERSION="8.1.1"
FFMPEG_SHA256="b6863adde98898f42602017462871b5f6333e65aec803fdd7a6308639c52edf3"
API_LEVEL=28

: "${ANDROID_NDK_HOME:?ANDROID_NDK_HOME doit pointer vers le NDK (r28c)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${SCRIPT_DIR}/../app/src/main/jniLibs/armeabi-v7a"
WORK_DIR="${WORK_DIR:-$(mktemp -d)}"
mkdir -p "${WORK_DIR}"
TOOLCHAIN="${ANDROID_NDK_HOME}/toolchains/llvm/prebuilt/linux-x86_64"
CC="${TOOLCHAIN}/bin/armv7a-linux-androideabi${API_LEVEL}-clang"

if [[ -x "${OUT_DIR}/libffmpeg.so" && -x "${OUT_DIR}/libffprobe.so" ]]; then
    echo "ffmpeg/ffprobe armeabi-v7a déjà présents dans ${OUT_DIR}"
    exit 0
fi

cd "${WORK_DIR}"
curl -fL --retry 5 --retry-delay 5 -o ffmpeg.tar.xz "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz"
echo "${FFMPEG_SHA256}  ffmpeg.tar.xz" | sha256sum -c -
tar -xf ffmpeg.tar.xz
cd "ffmpeg-${FFMPEG_VERSION}"

./configure \
    --enable-cross-compile --target-os=android --arch=arm --cpu=armv7-a \
    --cc="${CC}" --cxx="${CC}++" \
    --ar="${TOOLCHAIN}/bin/llvm-ar" --nm="${TOOLCHAIN}/bin/llvm-nm" \
    --ranlib="${TOOLCHAIN}/bin/llvm-ranlib" --strip="${TOOLCHAIN}/bin/llvm-strip" \
    --disable-gpl --disable-nonfree --disable-doc --disable-debug \
    --disable-ffplay --enable-ffmpeg --enable-ffprobe \
    --enable-small --enable-pic --enable-jni --enable-mediacodec \
    --disable-vulkan --disable-autodetect \
    --extra-cflags="-Os -fPIE" --extra-ldflags="-pie"

make -j"$(nproc)" ffmpeg ffprobe

mkdir -p "${OUT_DIR}"
"${TOOLCHAIN}/bin/llvm-strip" --strip-unneeded -o "${OUT_DIR}/libffmpeg.so" ffmpeg
"${TOOLCHAIN}/bin/llvm-strip" --strip-unneeded -o "${OUT_DIR}/libffprobe.so" ffprobe
chmod +x "${OUT_DIR}/libffmpeg.so" "${OUT_DIR}/libffprobe.so"
ls -l "${OUT_DIR}"
