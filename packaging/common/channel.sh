#!/usr/bin/env bash

BOBINE_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bobine_channel_of_version() {
    python3 "${BOBINE_COMMON_DIR}/channel.py" channel-of-version "$1"
}

install_channel_icons() {
    local channel="$1" icons_root="$2" dest="$3"
    local src="${icons_root}/${channel}" png size_dir
    if [ ! -d "${src}/hicolor" ]; then
        echo "Erreur: icônes du canal '${channel}' introuvables dans ${src} (lancer scripts/generate_channel_icons.py)." >&2
        return 1
    fi
    while IFS= read -r png; do
        size_dir="$(basename "$(dirname "$(dirname "$png")")")"
        for name in com.bobine.app bobine; do
            install -D -m 0644 "$png" "${dest}/usr/share/icons/hicolor/${size_dir}/apps/${name}.png"
        done
    done < <(find "${src}/hicolor" -path '*/apps/com.bobine.app.png' | sort)
    for name in com.bobine.app bobine; do
        install -D -m 0644 "${src}/pixmaps/com.bobine.app.png" "${dest}/usr/share/pixmaps/${name}.png"
    done
}
