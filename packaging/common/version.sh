#!/usr/bin/env bash
BOBINE_VERSION_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

split_bobine_version() {
    local parsed
    parsed="$(python3 "${BOBINE_VERSION_SH_DIR}/channel.py" package-fields "$1")" || return 1
    read -r BASE_VERSION CHANNEL RUN RPM_RELEASE ARCH_VERSION <<< "${parsed}"
}

bobine_package_arch() {
    case "$1" in
        x86_64|aarch64) echo "$1" ;;
        arm64) echo aarch64 ;;
        amd64) echo x86_64 ;;
        *) echo "Erreur: architecture non prise en charge : $1" >&2; return 1 ;;
    esac
}
