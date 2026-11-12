#!/usr/bin/env bash
BOBINE_VERSION_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

split_bobine_version() {
    local parsed
    parsed="$(python3 "${BOBINE_VERSION_SH_DIR}/channel.py" package-fields "$1")" || return 1
    read -r BASE_VERSION CHANNEL RUN RPM_RELEASE ARCH_VERSION <<< "${parsed}"
}
