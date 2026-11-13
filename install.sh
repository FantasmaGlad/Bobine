#!/usr/bin/env bash
set -Eeuo pipefail

ORIG_ARGS=("$@")
SELF_PATH="${BASH_SOURCE[0]:-}"
SCRIPT_NAME="$([[ -n "${SELF_PATH}" ]] && basename "${SELF_PATH}" || echo install.sh)"
if [[ -n "${SELF_PATH}" && -f "${SELF_PATH}" ]]; then
    REPO_DIR="$(cd "$(dirname "${SELF_PATH}")" && pwd)"
else
    REPO_DIR="${PWD}"
fi
SELF_SHA="$([[ -f "${SELF_PATH}" ]] && sha256sum "${SELF_PATH}" 2>/dev/null | cut -d' ' -f1 || true)"
SCRIPT_VERSION="$(cat "${REPO_DIR}/VERSION" 2>/dev/null || echo "5.2.2")"
CONFIG_DIR="/etc/bobine"

if [[ -t 1 ]] && [[ "${NO_COLOR:-}" != "1" ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
    BOLD=$(tput bold); DIM=$(tput dim); RESET=$(tput sgr0)
    WHITE=$(tput setaf 7 2>/dev/null || echo '')
    RED=$(tput setaf 1); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4); CYAN=$(tput setaf 6)
else
    BOLD=""; DIM=""; RESET=""; WHITE=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; CYAN=""
fi

ICON_OK="${GREEN}[OK]${RESET}"
ICON_FAIL="${RED}[ERREUR]${RESET}"
ICON_WARN="${YELLOW}[ATTENTION]${RESET}"
ICON_SKIP="${DIM}[-]${RESET}"
ICON_INFO="${BLUE}->${RESET}"

INSTALL_LANG=""

banner() {
    local cols
    cols=$(tput cols 2>/dev/null || echo 80)

    printf "\n"
    if (( cols >= 115 )); then
        printf "%s%s" "$WHITE" "$BOLD"
        cat <<'EOF'
   ████████████████████                                                                                                 
 ██████████████████████████                                                                                             
 ██    ██         ██   █████                                                                                            
 ██    ██         ██   ██████                                                                                           
 ██ ███████████████████████ ██                                                                                          
 █████████████████████████████                       ██████              ██████                                         
  ██████████        ███████ ██                       ██████              ██████                                         
   ██████████████████████   ██                       ██████              ██████                                         
   ██████████   █████  ███████                       ██████                                                             
   ██████        █████████████      █████████████    ████████████████    ██████  ████████████████      ████████████     
  █████          ██ ██    █████    ███████████████   █████████████████   ██████  █████████████████    ███████████████   
 █████                     ████   ███████    ██████  ████████   ████████ ██████  ████████   ███████  ██████     ██████  
██████       ██        ███  ████ ██████       ██████ ██████       ██████ ██████  ███████     ██████ ██████████████████  
██████        ██  ██        ████ ██████       ██████ ██████       ██████ ██████  ██████      ██████ ██████████████████  
███████████    ███  ████████████ ███████     ███████ ███████      ██████ ██████  ██████      ██████ ██████              
 ███ █████████████████████ █████  █████████████████  ██████████████████  ██████  ██████      ██████  ███████████████    
█████ █ █████████ ███ █████████    ███████████████   █████████████████   ██████  ██████      ██████   ███████████████   
 ████  ████████ ███ █   ███████       ██████████     ███████████████     ██████  ██████      ██████      ██████████     
  ███████████████████████████                                                                                           
     █████████████████████                                                                                              
EOF
        printf "%s" "$RESET"
    else
        printf '%s%s  Bobine%s %s· installateur v%s%s\n' "$BOLD" "$WHITE" "$RESET" "$DIM" "$SCRIPT_VERSION" "$RESET"
    fi
    if [[ "${INSTALL_LANG:-fr}" == "en" ]]; then
        printf '%s  Open-Source Video Playout & Streaming Suite for Gyms%s\n' "$DIM" "$RESET"
        printf '%s  Debian 13 (trixie) · Dell Wyse 5070 · FastAPI + Next.js (v%s)%s\n\n' "$DIM" "$SCRIPT_VERSION" "$RESET"
    else
        printf '%s  Régie Vidéo & Streaming Libre pour Salle de Sport%s\n' "$DIM" "$RESET"
        printf '%s  Debian 13 (trixie) · Dell Wyse 5070 · FastAPI + Next.js (v%s)%s\n\n' "$DIM" "$SCRIPT_VERSION" "$RESET"
    fi
}

usage() {
    cat <<EOF
${BOLD}${SCRIPT_NAME}${RESET} — installateur tout-en-un d'Bobine (v${SCRIPT_VERSION})

${BOLD}USAGE${RESET}
  sudo ./${SCRIPT_NAME} [options]

${BOLD}OPTIONS${RESET}
  -h, --help          Affiche cette aide et quitte
  -V, --version       Affiche la version et quitte
  -l, --lang=fr|en    Langue de l'installateur (fr: Français, en: English)
      --channel=stable|beta|canary
                        Canal de mise à jour (stable par défaut). Bêta donne un accès
                        anticipé à des lots de fonctionnalités choisis avant publication ;
                        Canary suit chaque commit de main, non testé. Dans les deux cas,
                        la prochaine version stable remplace toujours automatiquement.
  -y, --yes           Ne demande aucune confirmation (mode non-interactif)
  -v, --verbose       Mode verbeux : affiche l'intégralité des flux et logs de compilation en direct
  -q, --quiet         Mode silencieux : n'affiche que les erreurs et le bilan final
      --dry-run       N'applique aucun changement : affiche ce qui serait fait
      --no-kiosk      Installation "serveur" : backend seul, sans Chromium/X11/audio
                        (pour un poste de dev ou un serveur distinct de l'écran câblé)
      --skip-packages Ne touche pas aux paquets apt (suppose les dépendances système déjà en place)
      --skip-build    Ne reconstruit pas le frontend (suppose frontend/out déjà à jour)
      --as-user LOGIN Compte cible quand le script tourne en root DIRECT (Debian sans sudo, lancé via 'su -').
                        Le kiosk, les fichiers et les groupes GPU appartiendront à ce compte.
      --progress=json Émet une ligne JSON par étape (sortie machine) pour Bobine Deploy.
                        Une ligne = un évènement {run_begin|step|run_end} ; le journal humain reste inchangé.
      --check         Diagnostic de l'installation existante, sans rien modifier
      --uninstall     Arrête, désactive et retire tout ce que ce script a installé
      --purge         Avec --uninstall : retire aussi venv/, node_modules/, frontend/out/ et la config
      --purge-data    Avec --uninstall --purge : retire EN PLUS les médias importés (destructif, confirmation requise)

${BOLD}EXEMPLES${RESET}
  curl -fsSL https://github.com/FantasmaGlad/Bobine/releases/latest/download/install.sh | bash
                                                Installation en une commande : récupère le code, demande sudo si besoin
  curl -fsSL https://github.com/FantasmaGlad/Bobine/releases/download/canary/install.sh | bash -s -- --channel=canary
  sudo ./${SCRIPT_NAME}                       Installation standard (interface épurée par défaut)
  sudo ./${SCRIPT_NAME} --lang=en             Installation en anglais
  sudo ./${SCRIPT_NAME} --channel=beta        Rejoint le canal Bêta (lots curés)
  sudo ./${SCRIPT_NAME} --channel=canary      Rejoint le canal Canary (dernier commit, non testé)
  sudo ./${SCRIPT_NAME} -v                    Installation avec flux verbeux (logs détaillés en direct)
  sudo ./${SCRIPT_NAME} --no-kiosk            Backend seul, sur un serveur ou un poste de dev
  sudo ./${SCRIPT_NAME} --skip-packages       Réinstalle après un 'git pull' sans retoucher apt
  sudo ./${SCRIPT_NAME} --dry-run             Prévisualise toutes les actions sans rien changer
  sudo ./${SCRIPT_NAME} --check               Vérifie l'état des services et affiche un résumé
  sudo ./${SCRIPT_NAME} --uninstall --purge   Désinstalle complètement (conserve les médias importés)
  su - -c "\$PWD/${SCRIPT_NAME} --as-user <login> -y"   Machine SANS sudo : install en root direct pour le compte <login>

Journal complet de chaque exécution : /var/log/bobine/install-*.log
EOF
}

DRY_RUN=false
ASSUME_YES=false
NO_KIOSK=false
SKIP_PACKAGES=false
SKIP_BUILD=false
AS_USER=""
DO_CHECK=false
DO_UNINSTALL=false
DO_PURGE=false
DO_PURGE_DATA=false
VERBOSE=false
QUIET=false
PROGRESS=""
PROGRESS_JSON=false
UPDATE_CHANNEL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        -V|--version) echo "Bobine install.sh v${SCRIPT_VERSION}"; exit 0 ;;
        -l|--lang) INSTALL_LANG="${2:-}"; shift ;;
        -l=*|--lang=*) INSTALL_LANG="${1#*=}" ;;
        --channel) UPDATE_CHANNEL="${2:-}"; shift ;;
        --channel=*) UPDATE_CHANNEL="${1#*=}" ;;
        -y|--yes) ASSUME_YES=true ;;
        --dry-run) DRY_RUN=true ;;
        --no-kiosk) NO_KIOSK=true ;;
        --skip-packages) SKIP_PACKAGES=true ;;
        --skip-build) SKIP_BUILD=true ;;
        --as-user) AS_USER="${2:-}"; shift ;;
        --as-user=*) AS_USER="${1#*=}" ;;
        --progress=*) PROGRESS="${1#*=}" ;;
        --progress) PROGRESS="${2:-}"; shift ;;
        --check) DO_CHECK=true ;;
        --uninstall) DO_UNINSTALL=true ;;
        --purge) DO_PURGE=true ;;
        --purge-data) DO_PURGE_DATA=true ;;
        -v|--verbose) VERBOSE=true ;;
        -q|--quiet) QUIET=true ;;
        *) echo "Option inconnue : $1" >&2; echo; usage; exit 1 ;;
    esac
    shift
done

has_tty() {
    [[ -t 0 ]] && return 0
    [[ -r /dev/tty && -w /dev/tty ]] && (: </dev/tty) 2>/dev/null
}

select_installer_language() {
    if [[ -n "${INSTALL_LANG:-}" ]]; then
        case "${INSTALL_LANG,,}" in
            en*) INSTALL_LANG="en" ;;
            *)   INSTALL_LANG="fr" ;;
        esac
        return 0
    fi

    if $ASSUME_YES || ! has_tty; then
        if [[ "${LANG:-}" =~ ^en ]]; then
            INSTALL_LANG="en"
        else
            INSTALL_LANG="fr"
        fi
        return 0
    fi

    printf '\n%s  Langue de l'\''installateur / Installer language :%s\n' "$BOLD" "$RESET"
    printf '    %s1%s) Français (par défaut)\n' "$CYAN" "$RESET"
    printf '    %s2%s) English\n' "$CYAN" "$RESET"
    local reply
    read -r -p "$(printf '%s  Votre choix / Choice [1/2] (1) : %s' "$YELLOW" "$RESET")" reply </dev/tty || reply="1"
    case "$reply" in
        2|[eE][nN]*) INSTALL_LANG="en" ;;
        *)           INSTALL_LANG="fr" ;;
    esac
}

select_installer_language

select_update_channel() {
    if [[ -n "${UPDATE_CHANNEL:-}" ]]; then
        case "${UPDATE_CHANNEL,,}" in
            beta*)   UPDATE_CHANNEL="beta" ;;
            canary*) UPDATE_CHANNEL="canary" ;;
            *)       UPDATE_CHANNEL="stable" ;;
        esac
        return 0
    fi

    local previous=""
    [[ -f "${CONFIG_DIR}/update-channel" ]] && previous="$(cat "${CONFIG_DIR}/update-channel" 2>/dev/null || true)"

    if $ASSUME_YES || ! has_tty; then
        UPDATE_CHANNEL="${previous:-stable}"
        return 0
    fi

    printf '\n%s  Canal de mise à jour :%s\n' "$BOLD" "$RESET"
    printf '    %s1%s) Stable (par défaut, recommandé)\n' "$CYAN" "$RESET"
    printf '    %s2%s) Bêta — lots de fonctionnalités sélectionnés avant publication\n' "$CYAN" "$RESET"
    printf '    %s3%s) Canary — tout dernier commit de main, non testé\n' "$CYAN" "$RESET"
    local default_choice="1"
    case "${previous}" in
        beta)   default_choice="2" ;;
        canary) default_choice="3" ;;
    esac
    local reply
    read -r -p "$(printf '%s  Votre choix [1/2/3] (%s) : %s' "$YELLOW" "$default_choice" "$RESET")" reply </dev/tty || reply="${default_choice}"
    case "${reply:-$default_choice}" in
        2) UPDATE_CHANNEL="beta" ;;
        3) UPDATE_CHANNEL="canary" ;;
        *) UPDATE_CHANNEL="stable" ;;
    esac
}

select_update_channel

case "${PROGRESS}" in
    "")     ;;
    json)   PROGRESS_JSON=true ;;
    *)      echo "Valeur --progress inconnue : ${PROGRESS} (attendu : json)" >&2; exit 1 ;;
esac

t() { if [[ "${INSTALL_LANG:-fr}" == "en" ]]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

APT_OPTS=(-o Acquire::Retries=3 -o DPkg::Lock::Timeout=180)

SPINNER_ENABLED=false
if [[ -t 1 ]] && ! $VERBOSE && ! $QUIET && ! $PROGRESS_JSON && [[ "${TERM:-dumb}" != "dumb" ]]; then
    SPINNER_ENABLED=true
fi
SPIN_FRAMES=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
    *[Uu][Tt][Ff]-8*|*[Uu][Tt][Ff]8*) ;;
    *) SPIN_FRAMES=('|' '/' '-' '\') ;;
esac

_spin_wait() {
    local pid="$1" i=0 started=$SECONDS shown=false activity="" cols
    cols=$(tput cols 2>/dev/null || echo 80)
    local width=$(( cols - 14 ))
    (( width < 20 )) && width=20
    while kill -0 "$pid" 2>/dev/null; do
        if (( SECONDS - started >= 2 )); then
            shown=true
            if (( i % 5 == 0 )); then
                activity="$(tail -n 3 "${LOG_FILE}" 2>/dev/null | tr -d '\r' | tr -c '[:print:]\n' ' ' | grep -v '^[[:space:]]*$' | tail -n 1 | cut -c1-${width} || true)"
            fi
            printf '\r  %s%s%s %s%s%s %s%ds%s\033[K' "$CYAN" "${SPIN_FRAMES[i % ${#SPIN_FRAMES[@]}]}" "$RESET" \
                "$DIM" "${activity:-${CURRENT_STEP_TITLE:-…}}" "$RESET" "$DIM" "$(( SECONDS - started ))" "$RESET" >&3
        fi
        i=$(( i + 1 ))
        sleep 0.12
    done
    $shown && printf '\r\033[K' >&3
    return 0
}

log()  { $QUIET && return 0; printf '\n%s%s>%s %s\n' "$BOLD" "$CYAN" "$RESET" "$*"; }
ok()   { $QUIET && return 0; printf '  %s %s\n' "$ICON_OK" "$*"; }
warn() { printf '  %s %s%s%s\n' "$ICON_WARN" "$YELLOW" "$*" "$RESET" >&2; }
err()  { printf '  %s %s%s%s\n' "$ICON_FAIL" "$RED" "$*" "$RESET" >&2; }

confirm() {
    $ASSUME_YES && return 0
    local reply
    read -r -p "$(printf '%s%s%s [o/N] ' "$YELLOW" "$1" "$RESET")" reply </dev/tty || return 1
    [[ "$reply" =~ ^[oOyY]$ ]]
}

run() {
    if $DRY_RUN; then
        printf '  %s[dry-run]%s %s\n' "$DIM" "$RESET" "$*"
        return 0
    fi
    if $VERBOSE; then
        "$@"
    elif $SPINNER_ENABLED; then
        "$@" >>"${LOG_FILE}" 2>&1 &
        local pid=$!
        _spin_wait "$pid"
        wait "$pid"
    else
        "$@" >>"${LOG_FILE}" 2>&1
    fi
}

write_file() {
    if $DRY_RUN; then
        printf '  %s[dry-run]%s écrirait %s\n' "$DIM" "$RESET" "$1"
        cat >/dev/null
    else
        cat >"$1"
    fi
}

append_file() {
    if $DRY_RUN; then
        cat >/dev/null
    else
        cat >>"$1"
    fi
}

run_user() {
    if $DRY_RUN; then
        printf '  %s[dry-run]%s (utilisateur %s) %s\n' "$DIM" "$RESET" "${TARGET_USER}" "$*"
        return 0
    fi
    local cmd=()
    if command -v sudo >/dev/null 2>&1; then
        cmd=(sudo -u "${TARGET_USER}" -- "$@")
    else
        local home
        home="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
        cmd=(runuser -u "${TARGET_USER}" -- env "HOME=${home:-/home/${TARGET_USER}}" "$@")
    fi
    if $VERBOSE; then
        "${cmd[@]}"
    elif $SPINNER_ENABLED; then
        "${cmd[@]}" >>"${LOG_FILE}" 2>&1 &
        local pid=$!
        _spin_wait "$pid"
        wait "$pid"
    else
        "${cmd[@]}" >>"${LOG_FILE}" 2>&1
    fi
}

user_out() {
    if command -v sudo >/dev/null 2>&1; then
        sudo -H -u "${TARGET_USER}" -- "$@"
    else
        runuser -u "${TARGET_USER}" -- env "HOME=$(getent passwd "${TARGET_USER}" | cut -d: -f6)" "$@"
    fi
}

apt_optional() {
    if $DRY_RUN; then
        printf '  %s[dry-run]%s installerait (optionnel) %s\n' "$DIM" "$RESET" "$*"
        return 0
    fi
    local cmd=(apt-get "${APT_OPTS[@]}" install -y --no-install-recommends "$@")
    if $VERBOSE; then
        if "${cmd[@]}"; then
            ok "paquet installé : $*"
            return 0
        fi
    else
        if "${cmd[@]}" >>"${LOG_FILE}" 2>&1; then
            ok "paquet installé : $*"
            return 0
        fi
    fi
    warn "paquet indisponible, ignoré : $* (composant apt manquant ?)"
    return 1
}

ensure_apt_components() {
    local want=(contrib non-free non-free-firmware) changed=false f comp
    for f in /etc/apt/sources.list.d/*.sources; do
        [[ -f "$f" ]] || continue
        grep -qiE '^URIs:.*debian\.org' "$f" || continue
        grep -qiE '^Components:' "$f" || continue
        for comp in "${want[@]}"; do
            grep -iE '^Components:' "$f" | grep -qw "$comp" && continue
            [[ -f "${f}.bobine.bak" ]] || cp -a "$f" "${f}.bobine.bak"
            sed -i -E "s/^(Components:.*)$/\1 ${comp}/I" "$f"
            changed=true
        done
    done
    if [[ -f /etc/apt/sources.list ]] \
        && grep -qE '^[[:space:]]*deb[[:space:]].* main' /etc/apt/sources.list \
        && ! grep -qE '^[[:space:]]*deb[[:space:]].*(contrib|non-free)' /etc/apt/sources.list; then
        cp -a /etc/apt/sources.list /etc/apt/sources.list.bobine.bak
        sed -i -E '/^[[:space:]]*deb[[:space:]].* main/ s/ main/ main contrib non-free non-free-firmware/' /etc/apt/sources.list
        changed=true
    fi
    $changed && ok "composants apt (contrib/non-free/non-free-firmware) activés"
    $changed
}

BOBINE_REPO_URL="${BOBINE_REPO_URL:-https://github.com/FantasmaGlad/Bobine.git}"
BOBINE_INSTALL_URL="${BOBINE_INSTALL_URL:-https://github.com/FantasmaGlad/Bobine/releases/latest/download/install.sh}"

PASS_ARGS=(${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"} "--lang=${INSTALL_LANG}" "--channel=${UPDATE_CHANNEL}")

SUDO_ENV=()
for _v in BOBINE_DIR BOBINE_REPO_URL BOBINE_INSTALL_URL NO_COLOR; do
    [[ -n "${!_v:-}" ]] && SUDO_ENV+=("${_v}=${!_v}")
done
unset _v

is_standalone() { [[ ! -d "${REPO_DIR}/backend/app" || ! -d "${REPO_DIR}/frontend" ]]; }

_bootstrap_fail() {
    local rc=$?
    echo
    err "$(t "Échec de l'amorçage (code ${rc}). Journal : ${LOG_FILE:-?}" "Bootstrap failed (code ${rc}). Log: ${LOG_FILE:-?}")"
    if [[ -n "${LOG_FILE:-}" && -f "${LOG_FILE}" ]]; then
        tail -n 15 "${LOG_FILE}" | sed 's/^/  /' >&2 || true
    fi
    exit "$rc"
}

bootstrap_standalone() {
    trap _bootstrap_fail ERR
    exec 3>&1
    LOG_FILE="$(mktemp /tmp/bobine-bootstrap.XXXXXX.log)"
    banner
    log "$(t "Amorçage — ce script est lancé hors d'une copie de Bobine : récupération du code" "Bootstrap — this script runs outside a Bobine checkout: fetching the code")"

    if [[ -n "${BOBINE_BOOTSTRAPPED:-}" ]]; then
        err "$(t "Amorçage déjà effectué mais la copie obtenue est incomplète : ${REPO_DIR}" "Bootstrap already done but the checkout is incomplete: ${REPO_DIR}")"
        exit 1
    fi

    if [[ $EUID -ne 0 ]]; then
        if ! command -v sudo >/dev/null 2>&1; then
            err "$(t "Droits root requis et sudo est absent. Relancez en root : su - -c 'curl -fsSL ${BOBINE_INSTALL_URL} | bash -s -- --as-user <votre_login>'" "Root rights required and sudo is missing. Re-run as root: su - -c 'curl -fsSL ${BOBINE_INSTALL_URL} | bash -s -- --as-user <your_login>'")"
            exit 1
        fi
        local copy="${SELF_PATH}"
        if [[ -z "${copy}" || ! -f "${copy}" ]]; then
            copy="$(mktemp /tmp/bobine-install.XXXXXX.sh)"
            if ! curl -fsSL --retry 3 -o "${copy}" "${BOBINE_INSTALL_URL}"; then
                err "$(t "Téléchargement de l'installateur impossible (${BOBINE_INSTALL_URL}) — vérifiez la connexion Internet." "Could not download the installer (${BOBINE_INSTALL_URL}) — check the Internet connection.")"
                exit 1
            fi
        fi
        ok "$(t "Droits administrateur requis — demande via sudo" "Administrator rights required — asking through sudo")"
        exec sudo env ${SUDO_ENV[@]+"${SUDO_ENV[@]}"} bash "${copy}" "${PASS_ARGS[@]}"
    fi

    if [[ -n "${AS_USER}" ]]; then
        TARGET_USER="${AS_USER}"
    elif [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
        TARGET_USER="${SUDO_USER}"
    else
        err "$(t "Compte cible introuvable : lancez via sudo depuis votre compte, ou ajoutez --as-user <login>." "Target account not found: run through sudo from your account, or add --as-user <login>.")"
        exit 1
    fi
    if ! id "${TARGET_USER}" >/dev/null 2>&1; then
        err "$(t "Le compte '${TARGET_USER}' n'existe pas sur cette machine." "The account '${TARGET_USER}' does not exist on this machine.")"
        exit 1
    fi
    local home dest
    home="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
    dest="${BOBINE_DIR:-${home}/Bobine}"

    if $DRY_RUN; then
        printf '  %s[dry-run]%s %s\n' "$DIM" "$RESET" "$(t "clonerait ${BOBINE_REPO_URL} dans ${dest} puis relancerait l'installation" "would clone ${BOBINE_REPO_URL} into ${dest} then restart the installation")"
        exit 0
    fi

    if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1 || ! [[ -d /etc/ssl/certs ]]; then
        if ! command -v apt-get >/dev/null 2>&1; then
            err "$(t "git et curl sont requis (gestionnaire apt introuvable : installez-les puis relancez)." "git and curl are required (apt not found: install them and re-run).")"
            exit 1
        fi
        log "$(t "Installation de git et curl" "Installing git and curl")"
        export DEBIAN_FRONTEND=noninteractive
        run apt-get "${APT_OPTS[@]}" update -qq
        run apt-get "${APT_OPTS[@]}" install -y -qq --no-install-recommends git curl ca-certificates
        ok "git, curl"
    fi

    if [[ -d "${dest}/.git" ]]; then
        log "$(t "Copie existante détectée : ${dest} — mise à jour" "Existing checkout found: ${dest} — updating")"
        run_user git -C "${dest}" fetch --tags --force --quiet
    elif [[ -e "${dest}" && -n "$(ls -A "${dest}" 2>/dev/null)" ]]; then
        err "$(t "${dest} existe déjà et n'est pas une copie de Bobine — déplacez-le ou fixez BOBINE_DIR=/autre/chemin." "${dest} already exists and is not a Bobine checkout — move it or set BOBINE_DIR=/other/path.")"
        exit 1
    else
        log "$(t "Récupération du code dans ${dest}" "Fetching the code into ${dest}")"
        if ! run_user git clone --quiet --filter=blob:none "${BOBINE_REPO_URL}" "${dest}"; then
            warn "$(t "Clone allégé indisponible — nouvelle tentative en clone complet." "Partial clone unavailable — retrying with a full clone.")"
            run rm -rf "${dest}"
            if ! run_user git clone --quiet "${BOBINE_REPO_URL}" "${dest}"; then
                err "$(t "Impossible de cloner ${BOBINE_REPO_URL} — vérifiez Internet/DNS/proxy. Détails : ${LOG_FILE}" "Cannot clone ${BOBINE_REPO_URL} — check Internet/DNS/proxy. Details: ${LOG_FILE}")"
                exit 1
            fi
        fi
    fi

    local ref=""
    if [[ "${UPDATE_CHANNEL}" == "beta" || "${UPDATE_CHANNEL}" == "canary" ]]; then
        user_out git -C "${dest}" rev-parse --verify -q "refs/tags/${UPDATE_CHANNEL}" >/dev/null 2>&1 && ref="${UPDATE_CHANNEL}"
    else
        ref="$(user_out git -C "${dest}" tag --list 'V*' --sort=-v:refname 2>/dev/null | grep -E '^V[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)"
    fi
    if [[ -n "${ref}" ]]; then
        run_user git -C "${dest}" -c advice.detachedHead=false checkout --quiet "${ref}"
        ok "$(t "Version ${ref} (canal ${UPDATE_CHANNEL})" "Version ${ref} (${UPDATE_CHANNEL} channel)")"
    else
        warn "$(t "Aucun tag de release trouvé — branche par défaut utilisée." "No release tag found — using the default branch.")"
    fi

    ok "$(t "Code prêt — lancement de l'installation" "Code ready — starting the installation")"
    exec env BOBINE_BOOTSTRAPPED=1 bash "${dest}/install.sh" "${PASS_ARGS[@]}"
}

if is_standalone; then
    bootstrap_standalone
fi

STEP_TOTAL=19
STEP_CUR=0
STEP_START_TS=0
CURRENT_STEP_TITLE=""
CURRENT_STEP_SLUG=""
STEP_OPEN=false

_json_escape() { local s="$1"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; printf '%s' "$s"; }
_now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
_pct_start() { echo $(( (STEP_CUR - 1) * 100 / STEP_TOTAL )); }
_pct_done()  { echo $(( STEP_CUR * 100 / STEP_TOTAL )); }

emit_event() {
    $PROGRESS_JSON || return 0
    printf '{"bobine":1,"ts":"%s",%s}\n' "$(_now_iso)" "$1" >&3
}

emit_step() {
    $PROGRESS_JSON || return 0
    local extra=""
    [[ -n "${3:-}" ]] && extra=",\"detail\":\"$(_json_escape "$3")\""
    emit_event "\"event\":\"step\",\"status\":\"$1\",\"step\":${STEP_CUR},\"total\":${STEP_TOTAL},\"pct\":$2,\"slug\":\"${CURRENT_STEP_SLUG}\",\"title\":\"$(_json_escape "$CURRENT_STEP_TITLE")\"${extra}"
}

_close_step() {
    $STEP_OPEN || return 0
    STEP_OPEN=false
    emit_step "$1" "$(_pct_done)" "${2:-}"
}

step() {
    _close_step ok
    STEP_CUR=$((STEP_CUR + 1))
    STEP_START_TS=$SECONDS
    CURRENT_STEP_SLUG="$1"; shift
    CURRENT_STEP_TITLE="$*"
    STEP_OPEN=true
    if ! $QUIET; then
        printf '\n%s┃%s %s[%d/%d]%s %s%s%s\n' "$CYAN" "$RESET" "$DIM" "$STEP_CUR" "$STEP_TOTAL" "$RESET" "$BOLD" "$*" "$RESET"
    fi
    emit_step start "$(_pct_start)"
}
step_done() {
    if ! $QUIET; then
        printf '  %s (%ss)\n' "$ICON_OK" "$((SECONDS - STEP_START_TS))"
    fi
    _close_step ok
}
step_skip() {
    if ! $QUIET; then
        printf '  %s ignoré — %s\n' "$ICON_SKIP" "$*"
    fi
    _close_step skip "$*"
}

on_error() {
    local rc=$?
    echo
    err "Échec à l'étape [${STEP_CUR}/${STEP_TOTAL}] ${CURRENT_STEP_TITLE} (code ${rc})."
    if [[ -n "${LOG_FILE:-}" && -f "${LOG_FILE}" ]]; then
        err "Journal complet : ${LOG_FILE}"
        if ! $VERBOSE; then
            echo
            printf '%s--- Dernières lignes du journal (%s) ---%s\n' "$YELLOW" "${LOG_FILE}" "$RESET"
            tail -n 25 "${LOG_FILE}" | sed 's/^/  /' || true
            printf '%s------------------------------------------------------------%s\n' "$YELLOW" "$RESET"
        fi
    fi
    STEP_OPEN=false
    emit_step error "$(_pct_start)" "code ${rc}"
    emit_event "\"event\":\"run_end\",\"status\":\"error\",\"rc\":${rc},\"step\":${STEP_CUR},\"total\":${STEP_TOTAL}"
    exit "$rc"
}
trap on_error ERR

if [[ $EUID -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1 && [[ -n "${SELF_PATH}" && -f "${SELF_PATH}" ]]; then
        ok "$(t "Droits administrateur requis — relance via sudo" "Administrator rights required — re-running through sudo")"
        exec sudo env ${SUDO_ENV[@]+"${SUDO_ENV[@]}"} bash "${SELF_PATH}" "${PASS_ARGS[@]}"
    fi
    banner
    echo
    err "Ce script doit être lancé en root :"
    err "  • via sudo depuis ton compte : sudo ./${SCRIPT_NAME}"
    err "  • ou en root direct (Debian sans sudo) : su - -c \"\$PWD/${SCRIPT_NAME} --as-user <login>\""
    exit 1
fi

if [[ -n "${AS_USER}" ]]; then
    TARGET_USER="${AS_USER}"
elif [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    TARGET_USER="${SUDO_USER}"
else
    banner
    echo
    err "Impossible de déterminer le compte cible."
    err "Lance via 'sudo ./${SCRIPT_NAME}' depuis ton compte normal,"
    err "ou en root (su -) avec '--as-user <login>' — ex. su - -c \"\$PWD/${SCRIPT_NAME} --as-user <login> -y\"."
    exit 1
fi

if ! id "${TARGET_USER}" >/dev/null 2>&1; then
    banner; echo
    err "Le compte cible '${TARGET_USER}' n'existe pas sur cette machine."
    exit 1
fi
if [[ "${TARGET_USER}" == "root" ]]; then
    banner; echo
    err "Le compte cible ne peut pas être root (le kiosk et les fichiers doivent appartenir à un utilisateur normal)."
    exit 1
fi
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="${REPO_DIR}"

BACKEND_DIR="${REPO_DIR}/backend"
FRONTEND_DIR="${REPO_DIR}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv"
CONFIG_FILE="${CONFIG_DIR}/config.toml"
configured_port() {
    local value=""
    if [[ -r "${CONFIG_FILE}" ]]; then
        value=$(sed -nE 's/^[[:space:]]*port[[:space:]]*=[[:space:]]*([0-9]+).*/\1/p' "${CONFIG_FILE}" | head -n1)
    fi
    if [[ "${value}" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 )); then
        echo "${value}"
    else
        echo 1903
    fi
}
SERVICE_PORT="$(configured_port)"
KIOSK_URL="http://127.0.0.1:${SERVICE_PORT}/kiosk"
UNITS=(bobine-backend bobine-kiosk bobine-audio-guard bobine-redirect bobine-watchdog)

LOG_DIR="/var/log/bobine"
mkdir -p "${LOG_DIR}" 2>/dev/null || LOG_DIR="/tmp"
LOG_FILE="${LOG_DIR}/install-$(date +%Y%m%d-%H%M%S).log"
exec 3>&1
exec > >(tee -a "${LOG_FILE}") 2>&1

if $DO_UNINSTALL; then
    banner
    log "Désinstallation d'Bobine"
    echo "  Dépôt   : ${REPO_DIR}"
    echo "  Journal : ${LOG_FILE}"

    confirm "Arrêter et retirer tous les services Bobine ?" || { echo "Annulé."; exit 0; }

    for unit in "${UNITS[@]}"; do
        if systemctl list-unit-files "${unit}.service" &>/dev/null; then
            run systemctl disable --now "${unit}.service" 2>/dev/null || true
            run rm -f "/etc/systemd/system/${unit}.service"
            ok "${unit}.service retiré"
        else
            step_skip "${unit}.service non installé"
        fi
    done
    run systemctl disable --now bobine-watchdog.timer 2>/dev/null || true
    run rm -f /etc/systemd/system/bobine-watchdog.timer
    run rm -f /etc/systemd/system/bobine-display-hotplug.service /etc/udev/rules.d/90-bobine-display.rules
    run udevadm control --reload-rules 2>/dev/null || true
    run systemctl daemon-reload

    run rm -f /etc/sudoers.d/bobine
    run rm -f /etc/modprobe.d/bobine-audio.conf
    run rm -f /etc/wireplumber/wireplumber.conf.d/51-fix-jack-autoport.conf
    run rm -f /etc/systemd/system/powertop.service.d/10-audio-nopowersave.conf
    run rm -f /usr/local/bin/bobine
    run rm -f /etc/polkit-1/rules.d/49-bobine-storage.rules
    run rm -f /usr/local/sbin/bobine-uninstall
    if [ -f /etc/bobine/apt-daily-disabled ]; then
        run systemctl enable --now apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
        run rm -f /etc/bobine/apt-daily-disabled
    fi
    if [ -f "${REPO_DIR}/packaging/linux/firewall/configure-firewall" ]; then
        run sh "${REPO_DIR}/packaging/linux/firewall/configure-firewall" close || true
    fi
    run rm -f /etc/ufw/applications.d/bobine /usr/lib/firewalld/services/bobine.xml
    if command -v nft >/dev/null 2>&1; then
        run nft delete table ip olmc_redirect 2>/dev/null || true
    fi
    ok "Intégrations système (sudoers, audio, redirection, commande CLI) retirées."

    if $DO_PURGE; then
        warn "Suppression de la configuration, de l'environnement Python et du build frontend."
        run rm -rf "${CONFIG_DIR}"
        run rm -rf "${VENV_DIR}"
        run rm -rf "${FRONTEND_DIR}/out" "${FRONTEND_DIR}/node_modules"
        ok "Configuration, venv et build frontend retirés."

        if $DO_PURGE_DATA; then
            if confirm "${RED}Supprimer aussi les médias importés (${REPO_DIR}/data et l'ancien ${REPO_DIR}/backend/data) ? IRRÉVERSIBLE.${RESET}"; then
                run rm -rf "${REPO_DIR}/data"
                run rm -rf "${REPO_DIR}/backend/data"
                warn "Médias importés supprimés (nouvel et ancien emplacement)."
            else
                echo "  Médias conservés (${REPO_DIR}/data)."
            fi
        fi
    else
        echo "  ${ICON_INFO} Configuration (${CONFIG_DIR}), venv et données conservées — relance avec --purge pour les retirer aussi."
    fi

    log "Désinstallation terminée."
    exit 0
fi

BOX_WIDTH=70
box_line() {
    local text="$1" pad
    pad=$((BOX_WIDTH - 4 - ${#text}))
    (( pad < 0 )) && pad=0
    printf '%s│%s %s%*s%s│%s\n' "$DIM" "$RESET" "$text" "$pad" "" "$DIM" "$RESET"
}
box_rule() { printf '%s%s%s%s\n' "$DIM" "$1" "$(printf '─%.0s' $(seq 1 $((BOX_WIDTH - 2))))" "$2$RESET"; }
box_top()    { box_rule "┌" "┐"; }
box_mid()    { box_rule "├" "┤"; }
box_bottom() { box_rule "└" "┘"; }

do_check() {
    banner
    log "Diagnostic de l'installation"

    local port
    port="$(configured_port)"

    echo
    box_top
    box_line "  Bobine — diagnostic"
    box_mid
    for unit in "${UNITS[@]}"; do
        if systemctl list-unit-files "${unit}.service" &>/dev/null; then
            if systemctl is-active --quiet "${unit}.service"; then
                box_line "  [OK] ${unit}  actif"
            else
                box_line "  [ERREUR] ${unit}  $(systemctl is-active "${unit}.service" 2>/dev/null || echo inconnu)"
            fi
        else
            box_line "  [-] ${unit}  non installé"
        fi
    done
    box_mid
    if curl -fsS -o /dev/null -m 3 "http://127.0.0.1:${port}/api/health" 2>/dev/null; then
        box_line "  [OK] API backend répond (port ${port})"
    else
        box_line "  [ERREUR] API backend injoignable (port ${port})"
    fi
    if [[ -d "${FRONTEND_DIR}/out" ]]; then
        box_line "  [OK] build frontend présent ($(date -r "${FRONTEND_DIR}/out" '+%d/%m %H:%M' 2>/dev/null || echo date-inconnue))"
    else
        box_line "  [ERREUR] build frontend absent"
    fi
    [[ -d "${VENV_DIR}" ]] && box_line "  [OK] environnement Python présent" || box_line "  [ERREUR] environnement Python absent"
    if ! $NO_KIOSK; then
        box_mid
        if command -v aplay >/dev/null 2>&1 && aplay -l 2>/dev/null | grep -q '^card '; then
            box_line "  [OK] audio : $(aplay -l 2>/dev/null | grep -c '^card ') carte(s) détectée(s)"
        else
            box_line "  [ERREUR] audio : aucune carte détectée (aplay -l)"
        fi
        if command -v vainfo >/dev/null 2>&1 && vainfo 2>&1 | grep -qi 'VAProfileH264'; then
            box_line "  [OK] décodage matériel H.264 (VA-API) disponible"
        else
            box_line "  [ATTENTION] décodage matériel indisponible — repli logiciel (voir vainfo)"
        fi
    fi
    if git -C "${REPO_DIR}" rev-parse --short HEAD &>/dev/null; then
        local rev dirty extra=""
        rev=$(git -C "${REPO_DIR}" rev-parse --short HEAD)
        dirty=$(git -C "${REPO_DIR}" status --porcelain 2>/dev/null | wc -l)
        [[ "$dirty" -gt 0 ]] && extra="  (+${dirty} fichiers modifiés)"
        box_line "  -> révision ${rev}${extra}"
    fi
    box_bottom
    echo
    exit 0
}
$DO_CHECK && do_check

banner
echo
echo "  Dépôt        : ${REPO_DIR}"
echo "  Utilisateur  : ${TARGET_USER}"
echo "  Journal      : ${LOG_FILE}"
FLAGS_ACTIVE=""
$DRY_RUN && FLAGS_ACTIVE+="dry-run "
$NO_KIOSK && FLAGS_ACTIVE+="no-kiosk "
$SKIP_PACKAGES && FLAGS_ACTIVE+="skip-packages "
$SKIP_BUILD && FLAGS_ACTIVE+="skip-build "
$ASSUME_YES && FLAGS_ACTIVE+="non-interactif "
[[ -n "$FLAGS_ACTIVE" ]] && echo "  Options      : ${YELLOW}${FLAGS_ACTIVE}${RESET}"

if systemctl list-unit-files bobine-backend.service &>/dev/null; then
    echo "  Mode         : mise à jour d'une installation existante"
else
    echo "  Mode         : nouvelle installation"
fi

if [[ -r /etc/os-release ]]; then
    . /etc/os-release
    if [[ "${VERSION_CODENAME:-}" != "trixie" ]]; then
        warn "Ce script est prévu pour Debian 13 (trixie). Système détecté : ${PRETTY_NAME:-inconnu}. On continue quand même."
    fi
fi

preflight_network() {
    $DRY_RUN && return 0

    local hdr remote_ts local_ts skew
    hdr="$(curl -sI -m 8 http://deb.debian.org/ 2>/dev/null | tr -d '\r' | awk -F': ' 'tolower($1)=="date"{print $2; exit}' || true)"
    if [[ -n "${hdr}" ]] && remote_ts="$(date -u -d "${hdr}" +%s 2>/dev/null)"; then
        local_ts="$(date -u +%s)"
        skew=$(( remote_ts > local_ts ? remote_ts - local_ts : local_ts - remote_ts ))
        if (( skew > 600 )); then
            warn "$(t "Horloge système décalée de $(( skew / 60 )) min — resynchronisation." "System clock is off by $(( skew / 60 )) min — resynchronising.")"
            timedatectl set-ntp true >/dev/null 2>&1 || true
            sleep 3
            local_ts="$(date -u +%s)"
            if (( (remote_ts > local_ts ? remote_ts - local_ts : local_ts - remote_ts) > 600 )); then
                date -u -s "@${remote_ts}" >/dev/null 2>&1 || true
            fi
            ok "$(t "Horloge corrigée : $(date '+%Y-%m-%d %H:%M')" "Clock fixed: $(date '+%Y-%m-%d %H:%M')")"
        fi
    fi

    if ! curl -fsS -m 10 -o /dev/null https://github.com 2>/dev/null; then
        local msg
        msg="$(t "GitHub est injoignable depuis cette machine (Internet, DNS ou proxy)." "GitHub is unreachable from this machine (Internet, DNS or proxy).")"
        if $SKIP_PACKAGES && $SKIP_BUILD; then
            warn "${msg}"
        else
            err "${msg}"
            err "$(t "Vérifiez : câble réseau / Wi-Fi, 'ping 1.1.1.1', 'getent hosts github.com'." "Check: network cable / Wi-Fi, 'ping 1.1.1.1', 'getent hosts github.com'.")"
            exit 1
        fi
    fi
}
preflight_network

AVAIL_KB=$(df --output=avail -k "${REPO_DIR}" 2>/dev/null | tail -1 | tr -d ' ')
if [[ -n "${AVAIL_KB:-}" ]] && (( AVAIL_KB < 2 * 1024 * 1024 )); then
    warn "Moins de 2 Go disponibles sur $(df --output=target "${REPO_DIR}" | tail -1 | tr -d ' ') — l'import de vidéos réclame nettement plus d'espace."
fi

emit_event "\"event\":\"run_begin\",\"version\":\"${SCRIPT_VERSION}\",\"total\":${STEP_TOTAL},\"user\":\"$(_json_escape "${TARGET_USER}")\",\"repo\":\"$(_json_escape "${REPO_DIR}")\",\"log\":\"$(_json_escape "${LOG_FILE}")\",\"mode\":\"$($NO_KIOSK && echo server || echo kiosk)\",\"dry_run\":${DRY_RUN}"

step_update_channel() {
    step update-channel "Canal de mise à jour (Stable / Bêta / Canary)"
    mkdir -p "${CONFIG_DIR}" 2>/dev/null || true
    write_file "${CONFIG_DIR}/update-channel" <<< "${UPDATE_CHANNEL}"

    if [[ -d "${REPO_DIR}/.git" ]]; then
        run git -C "${REPO_DIR}" fetch --tags --force
        if [[ "${UPDATE_CHANNEL}" == "beta" || "${UPDATE_CHANNEL}" == "canary" ]]; then
            if git -C "${REPO_DIR}" rev-parse --verify -q "refs/tags/${UPDATE_CHANNEL}" >/dev/null; then
                TARGET_TAG="${UPDATE_CHANNEL}"
            else
                TARGET_TAG=""
            fi
        else
            TARGET_TAG="$(git -C "${REPO_DIR}" tag --list 'V*' --sort=-v:refname 2>/dev/null | grep -E '^V[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)"
        fi
        if [[ -n "${TARGET_TAG:-}" ]]; then
            CURRENT_TAG="$(git -C "${REPO_DIR}" describe --tags --exact-match 2>/dev/null || true)"
            if [[ "${CURRENT_TAG}" != "${TARGET_TAG}" ]]; then
                log "Bascule sur ${TARGET_TAG} (canal ${UPDATE_CHANNEL})"
                run git -C "${REPO_DIR}" checkout "${TARGET_TAG}"
                if [[ -z "${BOBINE_REEXEC:-}" && -n "${SELF_PATH}" && -f "${SELF_PATH}" ]] && ! $DRY_RUN \
                    && [[ "$(sha256sum "${SELF_PATH}" | cut -d' ' -f1)" != "${SELF_SHA}" ]]; then
                    ok "$(t "Installateur mis à jour par ce changement de version — relance" "Installer changed by this version switch — restarting")"
                    emit_event "\"event\":\"restart\",\"reason\":\"installer_updated\""
                    exec 1>&3 2>&3
                    exec env BOBINE_REEXEC=1 bash "${SELF_PATH}" "${PASS_ARGS[@]}"
                fi
            else
                ok "Déjà sur ${TARGET_TAG} (canal ${UPDATE_CHANNEL})"
            fi
        else
            warn "Aucun tag de release trouvé dans ce dépôt — installation depuis la branche courante (canal « ${UPDATE_CHANNEL} » enregistré, sans effet pour cette exécution)."
        fi
    else
        warn "${REPO_DIR} n'est pas un dépôt git — canal « ${UPDATE_CHANNEL} » enregistré mais sans effet sur les fichiers installés."
    fi
    step_done
}

step_packages() {
    step packages "Paquets système (apt)"
    if $SKIP_PACKAGES; then
        step_skip "--skip-packages"
    else
        export DEBIAN_FRONTEND=noninteractive
        run apt-get "${APT_OPTS[@]}" update -qq

        run apt-get "${APT_OPTS[@]}" install -y --no-install-recommends \
            ffmpeg \
            python3 \
            python3-venv \
            python3-pip \
            chromium \
            xinit \
            xserver-xorg \
            x11-xserver-utils \
            unclutter \
            vainfo \
            curl \
            ca-certificates \
            gnupg \
            sudo \
            avahi-daemon \
            udisks2 \
            smartmontools \
            exfatprogs \
            e2fsprogs \
            dosfstools \
            ntfs-3g \
            gvfs-backends \
            gvfs-fuse \
            libmtp-runtime \
            polkitd \
            dbus-user-session \
            nftables \
            alsa-utils \
            pipewire \
            pipewire-pulse \
            wireplumber \
            pulseaudio-utils
        ok "paquets système de base installés"

        GPU_LINES="$(lspci -nn 2>/dev/null | grep -Ei 'VGA compatible controller|3D controller|Display controller' || true)"
        HAS_INTEL_GPU=false; HAS_AMD_GPU=false; HAS_NVIDIA_GPU=false
        grep -qiE '\[8086:' <<<"$GPU_LINES" && HAS_INTEL_GPU=true
        grep -qiE '\[1002:' <<<"$GPU_LINES" && HAS_AMD_GPU=true
        grep -qiE '\[10de:' <<<"$GPU_LINES" && HAS_NVIDIA_GPU=true
        CPU_VENDOR="$(LC_ALL=C lscpu 2>/dev/null | awk -F: '/Vendor ID/{gsub(/^[ \t]+/,"",$2);print $2; exit}')"
        ok "matériel détecté — GPU: Intel=$HAS_INTEL_GPU AMD=$HAS_AMD_GPU NVIDIA=$HAS_NVIDIA_GPU | CPU=${CPU_VENDOR:-inconnu}"

        if $HAS_INTEL_GPU || $HAS_AMD_GPU || $HAS_NVIDIA_GPU; then
            if ! $DRY_RUN && ensure_apt_components; then
                run apt-get "${APT_OPTS[@]}" update -qq || true
            fi
        fi

        command -v qrencode >/dev/null 2>&1 || apt_optional qrencode || true

        case "$CPU_VENDOR" in
            *AuthenticAMD*|*AMD*)     apt_optional amd64-microcode ;;
            *GenuineIntel*|*Intel*)   apt_optional intel-microcode ;;
        esac

        if $HAS_INTEL_GPU; then
            apt_optional intel-media-va-driver-non-free || apt_optional intel-media-va-driver || apt_optional i965-va-driver
        fi
        if $HAS_AMD_GPU; then
            apt_optional mesa-va-drivers
            apt_optional firmware-amd-graphics
        fi
        if $HAS_NVIDIA_GPU && ! $HAS_INTEL_GPU && ! $HAS_AMD_GPU; then
            warn "GPU NVIDIA seul détecté : pas de pilote propriétaire installé (hors périmètre v1)."
            warn "Le décodage vidéo se fera en logiciel — surveiller la charge CPU sur l'écran réseau."
        fi

        apt_optional firmware-linux-free
        apt_optional firmware-misc-nonfree
        if ip -o link 2>/dev/null | grep -qiE ': wl'; then
            log "Interface Wi-Fi détectée : firmware sans fil"
            apt_optional firmware-iwlwifi
            apt_optional firmware-realtek
            apt_optional firmware-atheros
        fi

        if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | sed 's/^v//;s/\..*//')" -lt 20 ]]; then
            if $DRY_RUN; then
                echo "  ${DIM}[dry-run]${RESET} installerait Node.js 22.x LTS (NodeSource)"
            else
                log "Installation de Node.js 22.x LTS (NodeSource)"
                run bash -o pipefail -c 'curl -fsSL --retry 3 https://deb.nodesource.com/setup_22.x | bash -'
                run apt-get "${APT_OPTS[@]}" install -y nodejs
                ok "Node.js 22.x LTS installé : $(node -v 2>/dev/null || echo 'installé')"
            fi
        else
            ok "Node.js déjà présent : $(node -v)"
        fi
        step_done
    fi
}

step_gpu_access() {
    step gpu-access "Accès GPU (groupes render/video) & Xwrapper"
    if $NO_KIOSK; then
        step_skip "--no-kiosk"
    else
        run usermod -aG render,video "${TARGET_USER}"
        ok "${TARGET_USER} ajouté aux groupes render/video"
        if getent group bluetooth >/dev/null 2>&1; then
            run usermod -aG bluetooth "${TARGET_USER}"
            ok "${TARGET_USER} ajouté au groupe bluetooth"
        fi

        if $DRY_RUN; then
            echo "  ${DIM}[dry-run]${RESET} configurerait /etc/X11/Xwrapper.config (allowed_users=anybody)"
        else
            if [[ -f /etc/X11/Xwrapper.config ]]; then
                if grep -q '^allowed_users=' /etc/X11/Xwrapper.config; then
                    sed -i 's/^allowed_users=.*/allowed_users=anybody/' /etc/X11/Xwrapper.config
                else
                    echo 'allowed_users=anybody' >> /etc/X11/Xwrapper.config
                fi
            else
                printf 'allowed_users=anybody\nneeds_root_rights=yes\n' > /etc/X11/Xwrapper.config
            fi
            ok "Xwrapper.config configuré"
        fi
        step_done
    fi
}

step_python_env() {
    step python-env "Environnement Python & dépendances backend"
    if [[ ! -d "${VENV_DIR}" ]]; then
        run_user python3 -m venv "${VENV_DIR}"
        ok "venv créé : ${VENV_DIR}"
    else
        ok "venv déjà présent : ${VENV_DIR}"
    fi
    PIP_QUIET="-q"; $VERBOSE && PIP_QUIET=""
    run_user "${VENV_DIR}/bin/pip" install --upgrade pip ${PIP_QUIET}
    run_user "${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt" ${PIP_QUIET}
    step_done
}

step_frontend_build() {
    step frontend-build "Build du frontend Next.js"
    if $SKIP_BUILD; then
        step_skip "--skip-build"
        if [[ ! -d "${FRONTEND_DIR}/out" ]]; then
            err "frontend/out introuvable et --skip-build demandé : le backend n'aura rien à servir."
            exit 1
        fi
    else
        run_user bash -c "cd '${FRONTEND_DIR}' && npm install --no-audit --no-fund && npm run build"
        if [[ ! -d "${FRONTEND_DIR}/out" ]] && ! $DRY_RUN; then
            err "le build frontend n'a pas produit de dossier out/. Abandon."
            exit 1
        fi
        ok "build produit dans ${FRONTEND_DIR}/out"
        step_done
    fi
}

step_config() {
    step config "Configuration de production"
    log "Écriture de ${CONFIG_FILE}"
    run mkdir -p "${CONFIG_DIR}"
    run mkdir -p \
        "${REPO_DIR}/data/videos" "${REPO_DIR}/data/watched" "${REPO_DIR}/data/thumbnails" \
        "${REPO_DIR}/data/backgrounds" "${REPO_DIR}/data/backgrounds_watched" \
        "${REPO_DIR}/data/audio" "${REPO_DIR}/data/audio_watched" \
        "${REPO_DIR}/data/radio" "${REPO_DIR}/data/radio_covers" \
        "${REPO_DIR}/data/radio_announcements" "${REPO_DIR}/data/radio_watched" \
        "${REPO_DIR}/data/logs"
    run chown -R "${TARGET_USER}:${TARGET_USER}" "${REPO_DIR}/data"

    write_file "${CONFIG_FILE}" <<EOF
# Généré par install.sh ; après modification : sudo systemctl restart bobine-backend

[database]
database_url = "sqlite:///${REPO_DIR}/data/database.db"

[media]
media_dir = "${REPO_DIR}/data/videos"
watch_dir = "${REPO_DIR}/data/watched"
thumbnails_dir = "${REPO_DIR}/data/thumbnails"
backgrounds_dir = "${REPO_DIR}/data/backgrounds"
backgrounds_watch_dir = "${REPO_DIR}/data/backgrounds_watched"
audio_dir = "${REPO_DIR}/data/audio"
audio_watch_dir = "${REPO_DIR}/data/audio_watched"
radio_dir = "${REPO_DIR}/data/radio"
radio_covers_dir = "${REPO_DIR}/data/radio_covers"
radio_announcements_dir = "${REPO_DIR}/data/radio_announcements"
radio_watch_dir = "${REPO_DIR}/data/radio_watched"

[logs]
logs_dir = "${REPO_DIR}/data/logs"

[server]
host = "0.0.0.0"
port = ${SERVICE_PORT}

[playback]
wait_time_between_courses = 10
volume_default = 100
EOF
    ok "configuration écrite"

    if [[ -d "${REPO_DIR}/backend/data" ]]; then
        warn "Données héritées détectées dans ${REPO_DIR}/backend/data (ancien emplacement)."
        warn "Pour les unifier sous ${REPO_DIR}/data, arrête le backend puis lance :"
        warn "  ${VENV_DIR}/bin/python ${REPO_DIR}/scripts/migrate_unify_data_dirs.py --dry-run"
        warn "puis à nouveau sans --dry-run une fois le plan vérifié."
    fi
    step_done
}

step_cli_tool() {
    step cli-tool "Script de contrôle CLI 'bobine'"
    write_file /usr/local/bin/bobine <<EOF
#!/usr/bin/env bash
set -euo pipefail
SERVICES=(bobine-backend.service bobine-kiosk.service)

case "\${1:-}" in
    start)   sudo systemctl start "\${SERVICES[@]}" ;;
    stop)    sudo systemctl stop "\${SERVICES[@]}" ;;
    restart) sudo systemctl restart "\${SERVICES[@]}" ;;
    journal) journalctl -u bobine-backend -u bobine-kiosk -f ;;
    *)       exec "${VENV_DIR}/bin/python" "${BACKEND_DIR}/run_cli.py" "\$@" ;;
esac
EOF
    run chmod +x /usr/local/bin/bobine
    ok "commande 'bobine' installée"
}

step_uninstaller() {
    step uninstaller "Désinstalleur détaché (bouton « Désinstaller » de l'UI)"
    write_file /usr/local/sbin/bobine-uninstall <<EOF
#!/usr/bin/env bash
exec systemd-run --collect --unit=olmc-uninstall --description="Bobine uninstall" ${REPO_DIR}/install.sh --uninstall --purge --purge-data -y
EOF
    run chmod +x /usr/local/sbin/bobine-uninstall
    ok "désinstalleur '/usr/local/sbin/bobine-uninstall' installé"
    step_done
}

step_storage_access() {
    step storage-access "Autorisation des supports amovibles"
    run sh "${REPO_DIR}/packaging/storage/configure-storage-access" configure "${TARGET_USER}"
    step_done
}

step_backend_service() {
    step backend-service "Service systemd — backend FastAPI"
    write_file /etc/systemd/system/bobine-backend.service <<EOF
[Unit]
Description=Bobine - Backend FastAPI
After=network.target

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_USER}
WorkingDirectory=${BACKEND_DIR}
# BOBINE_PORT_STRICT=1 : pas de repli de port, la redirection 80 et le pare-feu visent ${SERVICE_PORT}
Environment=BOBINE_PORT=${SERVICE_PORT}
Environment=BOBINE_PORT_STRICT=1
ExecStart=${VENV_DIR}/bin/python ${BACKEND_DIR}/run_backend.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
    ok "bobine-backend.service écrit"
    step_done
}

step_kiosk() {
    step kiosk "Kiosk Chromium (écran cinéma câblé)"
    if $NO_KIOSK; then
        step_skip "--no-kiosk"
    else
        log "Configuration du kiosk Chromium (X11 dédié, sans display manager)"

        CHROMIUM_BIN="/usr/lib/chromium/chromium"
        if [[ ! -x "${CHROMIUM_BIN}" ]]; then
            warn "${CHROMIUM_BIN} introuvable, utilisation de /usr/bin/chromium à la place."
            warn "Le wrapper Debian charge plasma-browser-integration : à désinstaller si le kiosk se bloque en environnement non-Plasma."
            CHROMIUM_BIN="/usr/bin/chromium"
        fi

        write_file "${CONFIG_DIR}/kiosk-xinitrc" <<EOF
#!/bin/sh
# Généré par install.sh
CHROMIUM_BIN="${CHROMIUM_BIN}"
KIOSK_URL="${KIOSK_URL}"
EOF
        append_file "${CONFIG_DIR}/kiosk-xinitrc" <<'EOF'

xset s off
xset -dpms
xset s noblank

if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.1 -root &
fi

# sans gestionnaire de fenêtres, --kiosk n'est pas honoré : sortie connectée forcée en 0x0, géométrie explicite
OUTPUT=""
for _ in $(seq 1 15); do
    # sortie externe préférée à la dalle interne
    OUTPUT=$(xrandr --query | awk '/ connected/{ if ($1 !~ /^(eDP|LVDS|DSI)/) { print $1; found=1; exit } if (!first) first=$1 } END { if (!found && first) print first }')
    [ -n "${OUTPUT}" ] && break
    sleep 1
done
if [ -n "${OUTPUT}" ]; then
    xrandr --output "${OUTPUT}" --primary --auto --pos 0x0
    for OTHER in $(xrandr --query | awk '/connected/{print $1}'); do
        [ "${OTHER}" = "${OUTPUT}" ] || xrandr --output "${OTHER}" --off
    done
fi

SCREEN_SIZE=$(xrandr --query | awk -F'[ ,]+' '/current/{print $8"x"$10; exit}')
case "${SCREEN_SIZE}" in
    [0-9]*x[0-9]*) ;;
    *) SCREEN_SIZE="1920x1080" ;;
esac
SCREEN_W=${SCREEN_SIZE%x*}
SCREEN_H=${SCREEN_SIZE#*x}

# attendre le backend : sinon la page d'erreur de Chromium reste affichée
for _ in $(seq 1 60); do
    curl -fsS -o /dev/null "${KIOSK_URL%/kiosk}/api/health" && break
    sleep 1
done

# WirePlumber remet Auto-Mute Mode à chaque activation de profil : réappliqué à chaque lancement, sur chaque carte
for BOBINE_CARD in $(awk -F'[][]' '/^ *[0-9]+ \[/{print $2}' /proc/asound/cards 2>/dev/null | sed 's/[[:space:]]*$//'); do
    amixer -c "${BOBINE_CARD}" sset 'Auto-Mute Mode' 'Disabled' >/dev/null 2>&1 || true
    # volume matériel à 100 % : niveau ligne vers la table de mixage
    amixer -c "${BOBINE_CARD}" scontrols 2>/dev/null | sed -n "s/^Simple mixer control '\([^']*\)'.*/\1/p" | sort -u | while IFS= read -r BOBINE_CTRL; do
        case "${BOBINE_CTRL}" in
            # IEC958, Beep et Loopback exclus : sortie parasite sur certains codecs
            *[Mm]ic*|*Boost|Capture|"Input Source"|"Auto-Mute Mode"|IEC958*|Beep|Loopback) continue ;;
        esac
        amixer -c "${BOBINE_CARD}" sset "${BOBINE_CTRL}" 100% unmute >/dev/null 2>&1 || true
    done
    # prise combo TRRS : polarisation micro coupée, sinon bruit injecté par un câble TRS
    amixer -c "${BOBINE_CARD}" sset 'Capture' 0% nocap >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" sset 'Capture',1 0% nocap >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" sset 'Headset Mic Boost' 0 >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" sset 'Rear Mic Boost' 0 >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" cset name='Input Source' 'Rear Mic' >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" cset name='Input Source',index=1 'Rear Mic' >/dev/null 2>&1 || true
done
pactl list short sinks 2>/dev/null | cut -f1 | while IFS= read -r BOBINE_SINK; do
    pactl set-sink-volume "${BOBINE_SINK}" 100% >/dev/null 2>&1 || true
done

# profil Chromium jetable : pas de cache d'une ancienne version du frontend
KIOSK_PROFILE="/var/tmp/bobine-kiosk-profile"
rm -rf "${KIOSK_PROFILE}"

exec ${CHROMIUM_BIN} \
    --kiosk "${KIOSK_URL}" \
    --user-data-dir="${KIOSK_PROFILE}" \
    --window-position=0,0 \
    --window-size=${SCREEN_W},${SCREEN_H} \
    --no-first-run \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --autoplay-policy=no-user-gesture-required \
    --enable-features=AcceleratedVideoDecodeLinuxGL,VaapiVideoDecodeLinuxGL \
    --use-gl=egl \
    --enable-gpu-rasterization \
    --enable-zero-copy \
    --ignore-gpu-blocklist \
    --start-fullscreen \
    --check-for-update-interval=31536000 \
    --disable-background-networking \
    --disable-component-update \
    --disable-sync \
    --disable-domain-reliability \
    --disable-client-side-phishing-detection \
    --no-pings \
    --disable-breakpad \
    --disable-crash-reporter \
    --metrics-recording-only \
    --disable-features=Translate,OptimizationHints,MediaRouter,AutofillServerCommunication
EOF
        run chmod +x "${CONFIG_DIR}/kiosk-xinitrc"

        write_file /etc/systemd/system/bobine-kiosk.service <<EOF
[Unit]
Description=Bobine - Kiosk Chromium (écran cinéma)
After=bobine-backend.service
Requires=bobine-backend.service
Conflicts=getty@tty1.service

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_USER}
PAMName=login
TTYPath=/dev/tty1
StandardInput=tty
StandardOutput=journal
StandardError=journal
UtmpIdentifier=tty1
UtmpMode=user
Restart=always
RestartSec=2
# topologie mémorisée : bobine-display-hotplug ne redémarre le kiosque que si elle change
ExecStartPre=+${REPO_DIR}/scripts/bobine-display-hotplug.sh --record
ExecStart=/usr/bin/xinit ${CONFIG_DIR}/kiosk-xinitrc -- :0 vt1 -nolisten tcp

[Install]
WantedBy=multi-user.target
EOF
        ok "bobine-kiosk.service + kiosk-xinitrc écrits"

        run chmod +x "${REPO_DIR}/scripts/bobine-display-hotplug.sh"
        write_file /etc/systemd/system/bobine-display-hotplug.service <<EOF
[Unit]
Description=Bobine - Reconfiguration du kiosque au branchement d'un ecran
After=bobine-kiosk.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=${REPO_DIR}/scripts/bobine-display-hotplug.sh
EOF
        write_file /etc/udev/rules.d/90-bobine-display.rules <<'EOF'
ACTION=="change", SUBSYSTEM=="drm", ENV{HOTPLUG}=="1", TAG+="systemd", ENV{SYSTEMD_WANTS}+="bobine-display-hotplug.service"
EOF
        ok "hotplug des écrans (udev DRM + bobine-display-hotplug) écrit"
        step_done
    fi
}

step_audio() {
    step audio "Audio (auto-port, anti-sifflement, garde-fou hors session)"
    if $NO_KIOSK; then
        step_skip "--no-kiosk"
    else
        run mkdir -p /etc/wireplumber/wireplumber.conf.d
        write_file /etc/wireplumber/wireplumber.conf.d/51-fix-jack-autoport.conf <<'EOF'
monitor.alsa.rules = [
  {
    matches = [
      { device.name = "~alsa_card.pci.*" }
    ]
    actions = {
      update-props = {
        api.acp.auto-port = true
        api.acp.auto-profile = true
      }
    }
  }
]
EOF
        ok "commutation automatique de prise jack restaurée"

        write_file /etc/modprobe.d/bobine-audio.conf <<'EOF'
options snd-hda-intel power_save=0 power_save_controller=N
EOF
        if ! $DRY_RUN; then
            echo 0 > /sys/module/snd_hda_intel/parameters/power_save 2>/dev/null || true
            for BOBINE_PC in /sys/class/sound/card*/device/power/control; do
                [[ -e "${BOBINE_PC}" ]] && echo on > "${BOBINE_PC}" 2>/dev/null || true
            done
        fi
        ok "mise en veille du codec audio désactivée (HDA et USB)"

        if [[ -f /etc/systemd/system/powertop.service ]]; then
            run mkdir -p /etc/systemd/system/powertop.service.d
            write_file /etc/systemd/system/powertop.service.d/10-audio-nopowersave.conf <<'EOF'
[Service]
ExecStartPost=/bin/sh -c 'echo 0 > /sys/module/snd_hda_intel/parameters/power_save'
ExecStartPost=/bin/sh -c 'for pc in /sys/class/sound/card*/device/power/control; do [ -e "$pc" ] && echo on > "$pc"; done; true'
EOF
            ok "garde-fou powertop installé"
        fi

        write_file /usr/local/bin/bobine-audio-mute.sh <<'EOF'
#!/bin/sh
CARDS=$(awk -F'[][]' '/^ *[0-9]+ \[/{print $2}' /proc/asound/cards 2>/dev/null | sed 's/[[:space:]]*$//')
# carte pas encore énumérée au boot : échec explicite pour que systemd réessaie
[ -z "${CARDS}" ] && exit 1
for CARD in ${CARDS}; do
    amixer -c "${CARD}" scontrols 2>/dev/null | sed -n "s/^Simple mixer control '\([^']*\)'.*/\1/p" | sort -u | while IFS= read -r CTRL; do
        case "${CTRL}" in
            # IEC958, Beep et Loopback exclus : sortie parasite sur certains codecs
            *[Mm]ic*|*Boost|Capture|"Input Source"|"Auto-Mute Mode"|IEC958*|Beep|Loopback) continue ;;
        esac
        amixer -c "${CARD}" -q sset "${CTRL}" mute 2>/dev/null || true
    done
done
EOF
        run chmod +x /usr/local/bin/bobine-audio-mute.sh
        write_file /etc/systemd/system/bobine-audio-guard.service <<'EOF'
[Unit]
Description=Bobine - Coupe le son hors session kiosk
Before=bobine-kiosk.service
StartLimitIntervalSec=30
StartLimitBurst=20

[Service]
Type=oneshot
RemainAfterExit=yes
Restart=on-failure
RestartSec=1
ExecStart=/usr/local/bin/bobine-audio-mute.sh
ExecStop=/usr/local/bin/bobine-audio-mute.sh

[Install]
WantedBy=multi-user.target
EOF
        ok "garde-fou audio (silence hors session kiosk) écrit"
        step_done
    fi
}

step_sudoers() {
    step sudoers "Autorisation sudo restreinte (bouton de réinitialisation)"
    log "Autorisation sudo restreinte pour le redémarrage des services depuis l'UI"
    if $NO_KIOSK; then
        SUDOERS_UNITS="/usr/bin/systemctl restart bobine-backend.service"
    else
        SUDOERS_UNITS="/usr/bin/systemctl restart bobine-backend.service, /usr/bin/systemctl restart bobine-kiosk.service"
    fi
    SUDOERS_UNITS="${SUDOERS_UNITS}, /usr/local/sbin/bobine-uninstall"
    write_file /etc/sudoers.d/bobine <<EOF
# seules ces commandes sont autorisées sans mot de passe ; ne jamais élargir
${TARGET_USER} ALL=(root) NOPASSWD: ${SUDOERS_UNITS}
EOF
    if ! $DRY_RUN; then
        chmod 0440 /etc/sudoers.d/bobine
        if ! visudo -c -f /etc/sudoers.d/bobine >/dev/null 2>&1; then
            warn "Fichier sudoers généré invalide, suppression (le bouton de reset ne fonctionnera pas)"
            rm -f /etc/sudoers.d/bobine
        else
            ok "règle sudoers validée par visudo"
        fi
    fi
    step_done
}

step_ntp() {
    step ntp "Synchronisation NTP, sans tâche réseau quotidienne"
    if command -v timedatectl >/dev/null 2>&1; then
        run timedatectl set-ntp true
        ok "systemd-timesyncd activé"
    else
        warn "timedatectl introuvable — vérifier manuellement la synchronisation NTP du système"
    fi
    if systemctl list-unit-files apt-daily.timer &>/dev/null; then
        run systemctl disable --now apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
        write_file /etc/bobine/apt-daily-disabled <<<"apt-daily.timer apt-daily-upgrade.timer"
        ok "$(t "Tâches réseau quotidiennes d'apt désactivées" "Daily apt network jobs disabled")"
    fi
    step_done
}

step_mdns_redirect() {
    step mdns-redirect "URL locale (mDNS) & redirection du port 80"
    log "Publication du nom mDNS 'bobine.local' (avahi)"
    if $DRY_RUN; then
        echo "  ${DIM}[dry-run]${RESET} configurerait avahi-daemon.conf (host-name, IPv6 désactivé)"
    else
        AVAHI_CONF="/etc/avahi/avahi-daemon.conf"
        if grep -qE '^#?host-name=' "${AVAHI_CONF}"; then
            sed -i 's/^#\?host-name=.*/host-name=bobine/' "${AVAHI_CONF}"
        else
            sed -i '/^\[server\]/a host-name=bobine' "${AVAHI_CONF}"
        fi
        if grep -qE '^#?use-ipv6=' "${AVAHI_CONF}"; then
            sed -i 's/^#\?use-ipv6=.*/use-ipv6=no/' "${AVAHI_CONF}"
        else
            sed -i '/^\[server\]/a use-ipv6=no' "${AVAHI_CONF}"
        fi
    fi
    run systemctl unmask avahi-daemon.service avahi-daemon.socket >/dev/null 2>&1 || true

    run mkdir -p /etc/systemd/system/avahi-daemon.service.d
    write_file /etc/systemd/system/avahi-daemon.service.d/10-wait-network-online.conf <<'EOF'
[Unit]
After=network-online.target
Wants=network-online.target
EOF
    run systemctl daemon-reload
    run systemctl enable avahi-daemon >/dev/null 2>&1 || true
    if ! $DRY_RUN && ! systemctl restart avahi-daemon; then
        warn "Impossible de démarrer avahi-daemon : l'URL bobine.local ne sera pas publiée."
        warn "L'accès par adresse IP (http://<IP-du-Wyse>:${SERVICE_PORT}) reste fonctionnel."
    else
        ok "avahi-daemon actif"
    fi

    log "Redirection du port 80 vers ${SERVICE_PORT} (nftables)"
    write_file "${CONFIG_DIR}/redirect.nft" <<EOF
# create, delete, create : rechargement idempotent
table ip olmc_redirect
delete table ip olmc_redirect
table ip olmc_redirect {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        tcp dport 80 redirect to :${SERVICE_PORT}
    }
}
EOF
    write_file /etc/systemd/system/bobine-redirect.service <<EOF
[Unit]
Description=Bobine - Redirection port 80 vers ${SERVICE_PORT}
After=network-pre.target nftables.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f ${CONFIG_DIR}/redirect.nft
ExecStop=/usr/sbin/nft delete table ip olmc_redirect

[Install]
WantedBy=multi-user.target
EOF
    ok "redirection du port 80 configurée"

    if command -v ufw >/dev/null 2>&1 || command -v firewall-cmd >/dev/null 2>&1; then
        run install -D -m 0644 "${REPO_DIR}/packaging/linux/firewall/bobine.ufw" /etc/ufw/applications.d/bobine
        run install -D -m 0644 "${REPO_DIR}/packaging/linux/firewall/bobine.firewalld.xml" /usr/lib/firewalld/services/bobine.xml
        if run sh "${REPO_DIR}/packaging/linux/firewall/configure-firewall" open; then
            ok "pare-feu ouvert aux réseaux locaux (ufw ou firewalld)"
        else
            warn "pare-feu non configuré : ouvrez le port 1903 (et 1904 à 1913) aux réseaux locaux à la main"
        fi
    fi
    step_done
}

step_watchdog() {
    step watchdog "Chien de garde de santé (watchdog)"
    run chmod +x "${REPO_DIR}/scripts/watchdog.sh"
    write_file /etc/systemd/system/bobine-watchdog.service <<EOF
[Unit]
Description=Bobine - Chien de garde santé (redémarre un composant mort)
After=bobine-backend.service

[Service]
Type=oneshot
ExecStart=${REPO_DIR}/scripts/watchdog.sh
EOF
    write_file /etc/systemd/system/bobine-watchdog.timer <<'EOF'
[Unit]
Description=Bobine - Declenche le chien de garde sante periodiquement

[Timer]
OnBootSec=90s
OnUnitActiveSec=30s
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
    ok "chien de garde santé (watchdog) écrit"
    step_done
}

step_tuning() {
    step tuning "Optimisations système (gouverneur CPU, journal)"
    if $NO_KIOSK; then
        step_skip "--no-kiosk"
    else
        if [[ -d /sys/devices/system/cpu/cpu0/cpufreq ]]; then
            write_file /etc/systemd/system/bobine-cpu-governor.service <<'EOF'
[Unit]
Description=Bobine - Gouverneur CPU en mode performance

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do [ -e "$g" ] && echo performance > "$g"; done; true'

[Install]
WantedBy=multi-user.target
EOF
            run systemctl daemon-reload
            run systemctl enable --now bobine-cpu-governor.service
            ok "gouverneur CPU réglé sur performance"
        else
            warn "cpufreq indisponible sur ce matériel (CPU sans scaling ou virtualisé) — gouverneur laissé tel quel"
        fi

        run mkdir -p /etc/systemd/journald.conf.d
        write_file /etc/systemd/journald.conf.d/bobine.conf <<'EOF'
[Journal]
SystemMaxUse=200M
EOF
        if ! $DRY_RUN; then
            systemctl restart systemd-journald 2>/dev/null || true
        fi
        ok "journal systemd plafonné à 200 Mo"
        step_done
    fi
}

step_activation() {
    step activation "Activation des services & vérification de santé"
    run systemctl daemon-reload
    if ! $NO_KIOSK; then
        run systemctl enable bobine-audio-guard.service
        run systemctl restart bobine-audio-guard.service 2>/dev/null || run systemctl start bobine-audio-guard.service
    fi
    run systemctl enable bobine-backend.service
    run systemctl restart bobine-backend.service 2>/dev/null || run systemctl start bobine-backend.service
    run systemctl enable bobine-watchdog.timer
    run systemctl restart bobine-watchdog.timer 2>/dev/null || run systemctl start bobine-watchdog.timer
    if ! $NO_KIOSK; then
        run systemctl enable bobine-kiosk.service
        run systemctl restart bobine-kiosk.service 2>/dev/null || run systemctl start bobine-kiosk.service
        run udevadm control --reload-rules 2>/dev/null || true
    fi
    run systemctl enable bobine-redirect.service >/dev/null 2>&1 || true
    if ! $DRY_RUN && ! systemctl restart bobine-redirect.service; then
        warn "Redirection port 80 -> ${SERVICE_PORT} indisponible (nftables) : utiliser http://bobine.local:${SERVICE_PORT}."
    fi

    if ! $DRY_RUN; then
        log "Attente de la disponibilité de l'API backend"
        HEALTHY=false
        for _ in $(seq 1 20); do
            if curl -fsS -o /dev/null -m 2 "http://127.0.0.1:${SERVICE_PORT}/api/health" 2>/dev/null; then
                HEALTHY=true
                break
            fi
            sleep 1
        done
        if $HEALTHY; then
            ok "API backend en ligne sur le port ${SERVICE_PORT}"
        else
            warn "L'API backend ne répond pas encore après 20s — vérifie : journalctl -u bobine-backend -n 50"
        fi
    fi
    step_done
}

step_capabilities() {
    step capabilities "Vérification des capacités audio & vidéo"
    AUDIO_OK=false
    VAAPI_OK=false
    if $NO_KIOSK; then
        step_skip "--no-kiosk (aucune sortie locale attendue)"
    elif $DRY_RUN; then
        step_skip "--dry-run"
    else
        if command -v aplay >/dev/null 2>&1 && aplay -l 2>/dev/null | grep -q '^card '; then
            AUDIO_OK=true
            ok "carte(s) audio détectée(s) : $(aplay -l 2>/dev/null | grep -c '^card ')"
        else
            warn "aucune carte audio détectée par aplay -l — vérifier le matériel/les pilotes"
        fi
        if command -v vainfo >/dev/null 2>&1; then
            VAINFO_OUT="$(vainfo 2>&1 || true)"
            if grep -qi 'VAProfileH264' <<<"${VAINFO_OUT}"; then
                VAAPI_OK=true
                VAAPI_DRIVER="$(grep -oE 'Driver version: .*' <<<"${VAINFO_OUT}" | head -1)"
                ok "décodage matériel H.264 disponible (${VAAPI_DRIVER:-pilote VA-API actif})"
            else
                warn "aucun profil H.264 VA-API détecté — décodage logiciel probable (voir 'vainfo' pour le détail)"
            fi
        else
            warn "vainfo introuvable — impossible de vérifier le décodage matériel"
        fi
        step_done
    fi
}

step_update_channel
step_packages
step_gpu_access
step_python_env
step_frontend_build
step_config
step_cli_tool
step_uninstaller
step_storage_access
step_backend_service
step_kiosk
step_audio
step_sudoers
step_ntp
step_mdns_redirect
step_watchdog
step_tuning
step_activation
step_capabilities

echo
box_top
box_line "  Bobine — installation terminée"
box_mid
LAN_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") { print $(i + 1); exit }}' || true)"
[[ -n "${LAN_IP}" ]] || LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
box_line "  Admin      http://bobine.local"
if [[ -n "${LAN_IP}" ]]; then
    box_line "             http://${LAN_IP}  (si .local reste muet)"
else
    box_line "             http://127.0.0.1:${SERVICE_PORT}  (et http://<IP>:${SERVICE_PORT})"
fi
if ! $NO_KIOSK; then
    box_line "  Kiosk      ${KIOSK_URL}"
fi
box_line "  Config     ${CONFIG_FILE}"
box_line "  Journal    ${LOG_FILE}"
box_line "  Contrôle   bobine {start|stop|restart|journal}, puis bobine --help"
box_line "  Diagnostic sudo ./${SCRIPT_NAME} --check"
if ! $NO_KIOSK && ! $DRY_RUN; then
    box_mid
    box_line "  Audio      $($AUDIO_OK && echo 'OK' || echo 'À VÉRIFIER — voir aplay -l')"
    box_line "  Vidéo (VA-API) $($VAAPI_OK && echo 'OK (matériel)' || echo 'décodage logiciel — voir vainfo')"
fi
box_bottom
echo

if [[ -n "${LAN_IP:-}" ]] && ! $DRY_RUN && ! $QUIET && command -v qrencode >/dev/null 2>&1; then
    printf '  %s%s%s\n' "$BOLD" "$(t "Ouvrir l'admin depuis un téléphone :" "Open the admin from a phone:")" "$RESET"
    qrencode -t ANSIUTF8 -m 1 "http://${LAN_IP}" 2>/dev/null | sed 's/^/    /' || true
    echo
fi

emit_event "\"event\":\"run_end\",\"status\":\"ok\",\"pct\":100,\"total\":${STEP_TOTAL},\"healthy\":${HEALTHY:-false},\"audio\":${AUDIO_OK:-false},\"vaapi\":${VAAPI_OK:-false},\"url\":\"http://bobine.local\",\"lan_ip\":\"${LAN_IP:-}\",\"port\":${SERVICE_PORT},\"dry_run\":${DRY_RUN}"

if ! $DRY_RUN; then
    systemctl --no-pager --lines=0 status bobine-backend.service $($NO_KIOSK || echo bobine-kiosk.service) 2>/dev/null || true
fi

if ! $NO_KIOSK; then
    echo
    warn "L'appartenance aux groupes render/video ne s'applique qu'aux nouvelles sessions :"
    warn "un redémarrage complet de la machine est recommandé avant la première recette."
    warn "Après redémarrage, revérifie le décodage matériel :"
    warn "  vainfo   (doit lister les profils H.264/HEVC avec le pilote iHD)"
    warn "  chrome://gpu dans le kiosk, et 'intel_gpu_top' pendant une lecture"
fi
