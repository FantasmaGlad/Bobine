#!/bin/sh
# bobine-display-hotplug — redémarre le kiosque quand un écran est branché ou
# débranché (appliance Wyse / mini-PC headless, plan 4.0 P1-4).
#
# Pourquoi : la configuration de la sortie vidéo (xrandr, géométrie Chromium)
# n'était exécutée qu'UNE fois au démarrage de la session kiosque
# (kiosk-xinitrc) : un projecteur ou une TV branché après le boot restait noir.
# Redémarrer la session réutilise exactement cette logique déjà éprouvée (dont
# l'attente d'un EDID tardif), sans dupliquer la configuration ici.
#
# Déclenché par une règle udev DRM -> bobine-display-hotplug.service (jamais
# directement par udev, qui ne doit pas être bloqué). Ne redémarre QUE si
# l'ensemble des sorties connectées a réellement changé, après un délai
# d'anti-rebond (les évènements HPD arrivent en rafale pendant la négociation).
#
#   bobine-display-hotplug           évalue et redémarre si besoin
#   bobine-display-hotplug --record  mémorise la topologie courante (appelé au
#                                    démarrage du kiosque, ExecStartPre)
#
# Variables (tests uniquement) : BOBINE_DRM_ROOT, BOBINE_SIG_FILE,
# BOBINE_LOCK_FILE, BOBINE_DEBOUNCE, BOBINE_SYSTEMCTL.

DRM_ROOT="${BOBINE_DRM_ROOT:-/sys/class/drm}"
SIG_FILE="${BOBINE_SIG_FILE:-/run/bobine-display.sig}"
LOCK_FILE="${BOBINE_LOCK_FILE:-/run/bobine-display.lock}"
DEBOUNCE="${BOBINE_DEBOUNCE:-3}"
SYSTEMCTL="${BOBINE_SYSTEMCTL:-systemctl}"

# Liste triée des connecteurs DRM connectés (ex. « card0-HDMI-A-1 »).
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

# Une seule évaluation à la fois (rafale d'évènements).
exec 9>"${LOCK_FILE}"
if command -v flock >/dev/null 2>&1; then
    flock -n 9 || exit 0
fi

sleep "${DEBOUNCE}"
NEW="$(topology)"
OLD="$(cat "${SIG_FILE}" 2>/dev/null)"

# Aucune sortie connectée : rien à afficher, on mémorise seulement (le retour
# d'un écran déclenchera la différence).
if [ -z "${NEW}" ]; then
    printf '%s' "${NEW}" > "${SIG_FILE}"
    exit 0
fi

# Pas de référence (kiosque jamais démarré) ou topologie inchangée : rien à faire.
if [ "${NEW}" = "${OLD}" ]; then
    exit 0
fi

printf '%s' "${NEW}" > "${SIG_FILE}"
logger -t bobine-display "Topologie des écrans modifiée (« ${OLD} » -> « ${NEW} ») : redémarrage du kiosque" 2>/dev/null || true
"${SYSTEMCTL}" try-restart bobine-kiosk.service
exit 0
