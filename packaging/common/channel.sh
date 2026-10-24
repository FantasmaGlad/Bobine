#!/usr/bin/env bash
# Canal du build et icônes de lanceur par canal (paquets .deb, .rpm, Arch). À SOURCER.
#
# Le canal du BUILD (stable|beta|canary) fixe l'icône du lanceur : changer de canal dans les
# Réglages installe le paquet de l'autre canal, qui apporte donc sa propre icône. Il se lit
# dans la version du paquet, par la règle unique de backend/app/release_channel.py.
#
# Prérequis : python3. Les icônes sont dans packaging/linux/icons/<canal>/ (générées par
# scripts/generate_channel_icons.py) : une image par taille, installée sous les deux noms
# historiques (com.bobine.app et bobine) pour que les chemins des paquets ne changent pas.

BOBINE_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# bobine_channel_of_version <version> : affiche stable, beta ou canary.
# Formes acceptées : 5.0.5 · 5.0.5+canary.42 (champ Version: Debian) · 5.0.5-beta (fichier VERSION)
# · 5.0.5~beta. Tout autre suffixe est traité comme Stable, jamais deviné. La règle n'est pas
# réécrite en shell : elle est appliquée par backend/app/release_channel.py (via channel.py).
bobine_channel_of_version() {
    python3 "${BOBINE_COMMON_DIR}/channel.py" channel-of-version "$1"
}

# install_channel_icons <canal> <dossier icons> <racine de destination>
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
