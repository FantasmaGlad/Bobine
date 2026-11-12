#!/bin/sh

DRM_ROOT="${BOBINE_DRM_ROOT:-/sys/class/drm}"
SIG_FILE="${BOBINE_SIG_FILE:-/run/bobine-display.sig}"
LOCK_FILE="${BOBINE_LOCK_FILE:-/run/bobine-display.lock}"
DEBOUNCE="${BOBINE_DEBOUNCE:-3}"
SYSTEMCTL="${BOBINE_SYSTEMCTL:-systemctl}"

topology() {
    for status_file in "${DRM_ROOT}"/card*-*/status; do
        [ -r "${status_file}" ] || continue
        if [ "$(cat "${status_file}" 2>/dev/null)" = "connected" ]; then
            basename "$(dirname "${status_file}")"
        fi
    done | sort | tr '\n' ' '
}

if [ "$1" = "--record" ]; then
    topology > "${SIG_FILE}"
    exit 0
fi

exec 9>"${LOCK_FILE}"
if command -v flock >/dev/null 2>&1; then
    flock -n 9 || exit 0
fi

sleep "${DEBOUNCE}"
NEW="$(topology)"
OLD="$(cat "${SIG_FILE}" 2>/dev/null)"

if [ -z "${NEW}" ]; then
    printf '%s' "${NEW}" > "${SIG_FILE}"
    exit 0
fi

if [ "${NEW}" = "${OLD}" ]; then
    exit 0
fi

printf '%s' "${NEW}" > "${SIG_FILE}"
logger -t bobine-display "Topologie des écrans modifiée (« ${OLD} » -> « ${NEW} ») : redémarrage du kiosque" 2>/dev/null || true
"${SYSTEMCTL}" try-restart bobine-kiosk.service
exit 0
