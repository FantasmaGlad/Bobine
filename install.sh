#!/usr/bin/env bash
#
# install.sh — installateur tout-en-un d'Bobine
# Cible par défaut : Debian 13 (trixie) sur Dell Wyse 5070, Intel Gemini Lake.
#
# Usage rapide :
#   curl -fsSL https://github.com/FantasmaGlad/Bobine/releases/latest/download/install.sh | bash
#                                     # tout-en-un : récupère le code, demande sudo, installe
#   git clone <repo> Bobine && cd Bobine
#   ./install.sh                      # installation complète (kiosk + backend), sudo auto
#   ./install.sh --help               # toutes les options
#
# Idempotent : le relancer après un 'git pull' met à jour les dépendances,
# reconstruit le frontend et redémarre les services proprement.
#
set -euo pipefail

# Arguments d'origine, conservés tels quels pour pouvoir relancer ce script
# (élévation sudo, amorçage depuis un dépôt cloné, rechargement après un
# changement de version) sans rien perdre de ce que l'utilisateur a demandé.
ORIG_ARGS=("$@")
# Vide quand le script arrive par un tube (`curl … | bash`) : bash ne le lit
# alors pas depuis un fichier. L'ancienne écriture `${BASH_SOURCE[0]}` y
# plantait aussitôt sous `set -u` ("variable sans liaison") — la commande
# d'installation annoncée dans le README ne pouvait donc jamais fonctionner.
SELF_PATH="${BASH_SOURCE[0]:-}"
SCRIPT_NAME="$([[ -n "${SELF_PATH}" ]] && basename "${SELF_PATH}" || echo install.sh)"
# Calculé tôt (avant tout usage root/argparse) : sert à la fois au bandeau
# d'accueil ci-dessous et à REPO_DIR plus bas (cf. §"Cible" — même valeur,
# lue une seule fois pour éviter toute divergence entre les deux usages).
if [[ -n "${SELF_PATH}" && -f "${SELF_PATH}" ]]; then
    REPO_DIR="$(cd "$(dirname "${SELF_PATH}")" && pwd)"
else
    REPO_DIR="${PWD}"
fi
# Empreinte de CE fichier : après un changement de version (étape
# update-channel), un installateur modifié par le checkout doit se relancer
# lui-même — sinon l'ancienne logique d'installation s'appliquerait à du code
# plus récent.
SELF_SHA="$([[ -f "${SELF_PATH}" ]] && sha256sum "${SELF_PATH}" 2>/dev/null | cut -d' ' -f1 || true)"
# VERSION décrit le code installé ; le repli sert au script distribué seul.
SCRIPT_VERSION="$(cat "${REPO_DIR}/VERSION" 2>/dev/null || echo "5.0.7")"
# Déplacé ici (auparavant défini beaucoup plus bas, avec le reste du bloc
# "Cible") : nécessaire tôt pour select_update_channel(), qui lit/écrit le
# canal choisi (${CONFIG_DIR}/update-channel) avant même l'exécution du
# premier step().
CONFIG_DIR="/etc/bobine"

# ============================================================================
# 0. Affichage : couleurs, symboles, aide, arguments
#    (tout ce bloc doit fonctionner sans root, pour que --help reste utilisable)
# ============================================================================

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
      --progress=json Émet une ligne JSON par étape (sortie machine) pour l'assistant graphique.
                        Une ligne = un évènement {run_begin|step|run_end} ; le journal humain reste inchangé.
      --check         Diagnostic de l'installation existante, sans rien modifier
      --reset-devices-pin
                        Efface le code PIN de l'onglet Périphériques (présence physique requise) ; à redéfinir ensuite
                        depuis l'écran local de la machine
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
  su - -c "\$PWD/${SCRIPT_NAME} --as-user fanta -y"   Machine SANS sudo : install en root direct pour le compte 'fanta'

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
DO_RESET_DEVICES_PIN=false
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
        --reset-devices-pin) DO_RESET_DEVICES_PIN=true ;;
        --uninstall) DO_UNINSTALL=true ;;
        --purge) DO_PURGE=true ;;
        --purge-data) DO_PURGE_DATA=true ;;
        -v|--verbose) VERBOSE=true ;;
        -q|--quiet) QUIET=true ;;
        *) echo "Option inconnue : $1" >&2; echo; usage; exit 1 ;;
    esac
    shift
done

# Une saisie est-elle possible ? Vrai avec une entrée standard interactive, ET
# aussi quand le script arrive par un tube (`curl … | bash`, stdin = le script)
# mais qu'un terminal de contrôle existe : les questions (langue, canal) se
# posent alors sur /dev/tty au lieu d'être sautées silencieusement. Faux dans
# une automatisation sans terminal (CI, SSH sans PTY) : valeurs par défaut.
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

# Canal de mise à jour : "stable",
# "beta" ou "canary". Une réinstallation idempotente (--skip-packages après
# un 'git pull', cf. en-tête du script) reprend le canal précédemment
# choisi plutôt que de retomber sur stable à chaque relance. Ce choix n'est
# PAS relu par le backend (qui a sa propre source de vérité, le réglage
# `update_channel` en base, modifiable indépendamment depuis Réglages) : la
# persistance ci-dessous ne sert qu'à cette CLI elle-même, pour les
# relances/réinstallations ultérieures.
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

# --progress=json : sortie machine (une ligne JSON par évènement) pour piloter
# une barre de progression depuis l'assistant graphique. Seule la valeur 'json' est gérée.
case "${PROGRESS}" in
    "")     ;;
    json)   PROGRESS_JSON=true ;;
    *)      echo "Valeur --progress inconnue : ${PROGRESS} (attendu : json)" >&2; exit 1 ;;
esac

# Texte bilingue des messages ajoutés après la sélection de langue :
# t "français" "english".
t() { if [[ "${INSTALL_LANG:-fr}" == "en" ]]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

# Options communes à tous les appels apt-get : `Acquire::Retries` absorbe les
# coupures réseau ponctuelles, `DPkg::Lock::Timeout` attend (jusqu'à 3 min) le
# verrou tenu par unattended-upgrades juste après le premier démarrage d'une
# Debian fraîche — sans ça l'installation échouait aléatoirement avec « Could
# not get lock /var/lib/dpkg/lock-frontend ».
APT_OPTS=(-o Acquire::Retries=3 -o DPkg::Lock::Timeout=180)

# Indicateur de progression animé pour les étapes longues (apt, pip, npm…).
# Actif uniquement sur un vrai terminal, hors mode verbeux/silencieux et hors
# sortie machine (--progress=json) ; dessiné sur le fd 3 (terminal d'origine)
# pour ne jamais polluer le journal. N'apparaît qu'au bout de 2 s : les
# commandes brèves restent silencieuses, sans clignotement.
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
            # Dernière ligne utile du journal : montre que ça travaille
            # vraiment (paquet en cours, module pip, étape npm…).
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

# Exécute une commande "atomique" en respectant --dry-run et la verbosité.
# En mode épuré par défaut, la sortie est redirigée vers LOG_FILE.
# En mode verbeux (-v/--verbose), la sortie est diffusée en direct à l'écran.
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

# Écrit (ou tronque) un fichier depuis un heredoc, en respectant --dry-run.
write_file() {
    if $DRY_RUN; then
        printf '  %s[dry-run]%s écrirait %s\n' "$DIM" "$RESET" "$1"
        cat >/dev/null
    else
        cat >"$1"
    fi
}

# Idem en ajout (deuxième moitié d'un fichier généré en deux temps, ex.
# kiosk-xinitrc : en-tête interpolée puis corps littéral).
append_file() {
    if $DRY_RUN; then
        cat >/dev/null
    else
        cat >>"$1"
    fi
}

# Exécute une commande EN TANT QUE TARGET_USER. Préfère `sudo -u` (comportement
# éprouvé du chemin classique) et retombe sur `runuser` (util-linux, toujours
# présent) quand sudo est absent — indispensable au chemin --as-user (Debian
# minimal sans sudo, lancé en root via 'su -'). Respecte --dry-run et la verbosité.
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

# Exécute une commande en tant que TARGET_USER et laisse sa sortie à l'appelant
# (lecture : tags git, chemins…) — pas de journalisation ni de spinner.
user_out() {
    if command -v sudo >/dev/null 2>&1; then
        sudo -H -u "${TARGET_USER}" -- "$@"
    else
        runuser -u "${TARGET_USER}" -- env "HOME=$(getent passwd "${TARGET_USER}" | cut -d: -f6)" "$@"
    fi
}

# Installe un paquet OPTIONNEL : ne fait JAMAIS échouer l'installation s'il est
# indisponible (ex. composant apt non activé) — simple avertissement. Sert à la
# détection matérielle : on tente le meilleur paquet pour le GPU/CPU présent.
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

# Active les composants contrib/non-free/non-free-firmware sur les sources
# Debian officielles s'ils manquent (requis par firmwares & pilotes non libres,
# séparés en composants distincts depuis Debian 12). Idempotent ; sauvegarde
# .bobine.bak avant toute édition. Gère le format deb822 (défaut de Debian 13)
# et l'ancien /etc/apt/sources.list.
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

# ============================================================================
# 0 bis. Amorçage — installation en une commande, sans dépôt local
#    curl -fsSL https://github.com/FantasmaGlad/Bobine/releases/latest/download/install.sh | bash
# ============================================================================
BOBINE_REPO_URL="${BOBINE_REPO_URL:-https://github.com/FantasmaGlad/Bobine.git}"
BOBINE_INSTALL_URL="${BOBINE_INSTALL_URL:-https://github.com/FantasmaGlad/Bobine/releases/latest/download/install.sh}"

# Arguments relayés tels quels à toute relance de ce script, avec la langue et
# le canal DÉJÀ choisis (aucune question posée deux fois).
PASS_ARGS=(${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"} "--lang=${INSTALL_LANG}" "--channel=${UPDATE_CHANNEL}")

# Variables d'environnement utiles relayées à travers sudo SANS `sudo -E` (qui
# exige un droit SETENV absent de nombreuses politiques sudoers).
SUDO_ENV=()
for _v in BOBINE_DIR BOBINE_REPO_URL BOBINE_INSTALL_URL NO_COLOR; do
    [[ -n "${!_v:-}" ]] && SUDO_ENV+=("${_v}=${!_v}")
done
unset _v

# Ce script ne se trouve pas dans une copie complète de Bobine : lancé par un
# tube (`curl … | bash`) ou copié seul. Il lui faut alors récupérer le code.
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

    # 1. Privilèges : sudo si disponible, sinon consigne précise.
    if [[ $EUID -ne 0 ]]; then
        if ! command -v sudo >/dev/null 2>&1; then
            err "$(t "Droits root requis et sudo est absent. Relancez en root : su - -c 'curl -fsSL ${BOBINE_INSTALL_URL} | bash -s -- --as-user <votre_login>'" "Root rights required and sudo is missing. Re-run as root: su - -c 'curl -fsSL ${BOBINE_INSTALL_URL} | bash -s -- --as-user <your_login>'")"
            exit 1
        fi
        local copy="${SELF_PATH}"
        if [[ -z "${copy}" || ! -f "${copy}" ]]; then
            # Script reçu par un tube : impossible de le relancer tel quel
            # sous sudo, on en télécharge une copie identique.
            copy="$(mktemp /tmp/bobine-install.XXXXXX.sh)"
            if ! curl -fsSL --retry 3 -o "${copy}" "${BOBINE_INSTALL_URL}"; then
                err "$(t "Téléchargement de l'installateur impossible (${BOBINE_INSTALL_URL}) — vérifiez la connexion Internet." "Could not download the installer (${BOBINE_INSTALL_URL}) — check the Internet connection.")"
                exit 1
            fi
        fi
        ok "$(t "Droits administrateur requis — demande via sudo" "Administrator rights required — asking through sudo")"
        exec sudo env ${SUDO_ENV[@]+"${SUDO_ENV[@]}"} bash "${copy}" "${PASS_ARGS[@]}"
    fi

    # 2. Compte cible : propriétaire du code, du kiosk et des données.
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

    # 3. Prérequis minimaux (une Debian netinst n'a ni git ni curl).
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

    # 4. Code : clone léger (sans les blobs d'historique) ou mise à jour.
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

    # 5. Version : dernière Stable, ou tag mobile `beta`/`canary` (nom de
    # tag == nom de canal pour les deux canaux rolling).
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

# Nombre d'appels à step() ci-dessous (mettre à jour si on en ajoute/retire).
# Cohérence garantie par la CI (job « install.sh sanity ») qui compare cette
# valeur à `grep -cE '^\s*step ' install.sh` : un ajout d'étape sans mise à jour
# ici casse le build (et fausserait le pourcentage de --progress=json).
STEP_TOTAL=19
STEP_CUR=0
STEP_START_TS=0
CURRENT_STEP_TITLE=""
CURRENT_STEP_SLUG=""
STEP_OPEN=false

# ---- Sortie machine (--progress=json) ----------------------------------------
# Émet une ligne JSON compacte par évènement sur le fd 3 (stdout d'origine,
# préservé avant la redirection vers tee) : l'assistant graphique la parse pour
# une barre de progression + un journal repliable, sans que ces lignes polluent
# le fichier journal humain. Schéma versionné par la clé de tête "bobine":1
# (le consommateur filtre les lignes qui matchent ^\{"bobine":). Silencieux hors
# --progress=json.
# Astuce SSH : allouer un PTY pour un flush ligne à ligne côté assistant.
_json_escape() { local s="$1"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; printf '%s' "$s"; }
_now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
_pct_start() { echo $(( (STEP_CUR - 1) * 100 / STEP_TOTAL )); }
_pct_done()  { echo $(( STEP_CUR * 100 / STEP_TOTAL )); }

emit_event() {
    $PROGRESS_JSON || return 0
    printf '{"bobine":1,"ts":"%s",%s}\n' "$(_now_iso)" "$1" >&3
}

# Émet l'évènement d'une étape. $1=status (start|ok|skip|error), $2=pct,
# $3=détail optionnel (raison d'un skip, code d'erreur…).
emit_step() {
    $PROGRESS_JSON || return 0
    local extra=""
    [[ -n "${3:-}" ]] && extra=",\"detail\":\"$(_json_escape "$3")\""
    emit_event "\"event\":\"step\",\"status\":\"$1\",\"step\":${STEP_CUR},\"total\":${STEP_TOTAL},\"pct\":$2,\"slug\":\"${CURRENT_STEP_SLUG}\",\"title\":\"$(_json_escape "$CURRENT_STEP_TITLE")\"${extra}"
}

# Clôt l'étape courante une seule fois (émet ok/skip). Permet à step() de clore
# automatiquement une étape qui n'a pas appelé step_done (ex. « Script de
# contrôle CLI »), tout en évitant un double évènement quand step_done/step_skip
# l'ont déjà close.
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

# ============================================================================
# 1. Vérifications préalables
# ============================================================================

if [[ $EUID -ne 0 ]]; then
    # Plutôt que d'échouer et d'obliger à retaper la commande : relance
    # automatique sous sudo (le mot de passe est demandé par sudo lui-même).
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

# Compte cible (propriétaire des fichiers, service kiosk, groupes GPU) :
#  - chemin classique : SUDO_USER (le compte ayant lancé sudo) ;
#  - chemin --as-user (root direct via 'su -', machine sans sudo) : le login fourni explicitement.
if [[ -n "${AS_USER}" ]]; then
    TARGET_USER="${AS_USER}"
elif [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    TARGET_USER="${SUDO_USER}"
else
    banner
    echo
    err "Impossible de déterminer le compte cible."
    err "Lance via 'sudo ./${SCRIPT_NAME}' depuis ton compte normal,"
    err "ou en root (su -) avec '--as-user <login>' — ex. su - -c \"\$PWD/${SCRIPT_NAME} --as-user fanta -y\"."
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
# Root (via `su -`, chemin --as-user) exécutant git dans un dépôt appartenant
# au compte cible : git refuse par défaut ("detected dubious ownership") et
# l'étape de canal échouait donc sur les Debian sans sudo. Autorisation
# limitée à CE dépôt, par l'environnement (git >= 2.31) — la configuration
# globale de root n'est jamais modifiée.
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="${REPO_DIR}"

BACKEND_DIR="${REPO_DIR}/backend"
FRONTEND_DIR="${REPO_DIR}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv"
CONFIG_FILE="${CONFIG_DIR}/config.toml"
# Port d'écoute : celui de /etc/bobine/config.toml si l'administrateur l'a déjà fixé (relance de
# l'installateur), sinon 8000. Sur l'appliance le port est déterministe (BOBINE_PORT_STRICT=1 dans
# l'unité du backend) : la redirection 80 -> port, les signets et la documentation supposent ce port.
configured_port() {
    local value=""
    if [[ -r "${CONFIG_FILE}" ]]; then
        value=$(sed -nE 's/^[[:space:]]*port[[:space:]]*=[[:space:]]*([0-9]+).*/\1/p' "${CONFIG_FILE}" | head -n1)
    fi
    if [[ "${value}" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 )); then
        echo "${value}"
    else
        echo 8000
    fi
}
SERVICE_PORT="$(configured_port)"
KIOSK_URL="http://127.0.0.1:${SERVICE_PORT}/kiosk"
UNITS=(bobine-backend bobine-kiosk bobine-audio-guard bobine-redirect bobine-watchdog)

LOG_DIR="/var/log/bobine"
mkdir -p "${LOG_DIR}" 2>/dev/null || LOG_DIR="/tmp"
LOG_FILE="${LOG_DIR}/install-$(date +%Y%m%d-%H%M%S).log"
# fd 3 = canal des évènements JSON (--progress=json) : on garde le stdout
# d'origine AVANT de dérouter le stdout "humain" vers tee. Les évènements
# atteignent ainsi l'assistant (même canal SSH) sans être écrits au journal.
exec 3>&1
exec > >(tee -a "${LOG_FILE}") 2>&1

# ---- Dispatch : réinitialisation du PIN « Périphériques » ----
if $DO_RESET_DEVICES_PIN; then
    DEVICES_DB="${REPO_DIR}/data/database.db"
    if [[ ! -f "${DEVICES_DB}" ]]; then
        echo "Base de données introuvable : ${DEVICES_DB}" >&2
        exit 1
    fi
    "${REPO_DIR}/backend/.venv/bin/python" - "${DEVICES_DB}" <<'PY'
import sqlite3
import sys

con = sqlite3.connect(sys.argv[1])
con.execute("DELETE FROM settings WHERE key = 'devices_pin_hash'")
con.commit()
con.close()
PY
    echo "Code PIN des périphériques effacé. Redéfinissez-le depuis l'écran local (Périphériques)."
    exit 0
fi

# ---- Dispatch : désinstallation ----
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
    # Le chien de garde est piloté par un TIMER (l'unité .service ci-dessus est
    # déclenchée par lui) : retirer aussi le timer.
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
                # Ancien emplacement historique : audio/fonds/logs pouvaient y résider avant unification
                # — sans cette ligne ils survivaient à un --purge-data (orphelins).
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

# ---- Dispatch : diagnostic seul ----
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
    # Même vérification qu'en fin d'installation, rejouable à tout moment sans
    # réinstaller quoi que ce soit.
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

# ============================================================================
# Installation
# ============================================================================

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

# Contrôles réseau AVANT toute modification : un échec ici est expliqué en une
# phrase au lieu de surgir plus tard comme une erreur apt ou git obscure.
preflight_network() {
    $DRY_RUN && return 0

    # Horloge : une pile CMOS à plat (fréquent sur un mini PC d'occasion) rend
    # les certificats TLS « pas encore valides » et fait échouer apt. On lit
    # l'en-tête Date d'un miroir Debian en HTTP simple (indépendant de TLS).
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

    # Accès Internet : requis pour apt/git/npm sauf réinstallation locale.
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

# Début de la séquence pilotable : métadonnées d'exécution pour l'assistant.
emit_event "\"event\":\"run_begin\",\"version\":\"${SCRIPT_VERSION}\",\"total\":${STEP_TOTAL},\"user\":\"$(_json_escape "${TARGET_USER}")\",\"repo\":\"$(_json_escape "${REPO_DIR}")\",\"log\":\"$(_json_escape "${LOG_FILE}")\",\"mode\":\"$($NO_KIOSK && echo server || echo kiosk)\",\"dry_run\":${DRY_RUN}"

# ---------------------------------------------------------------------------
step update-channel "Canal de mise à jour (Stable / Bêta / Canary)"
# ---------------------------------------------------------------------------
# Persiste le choix pour les relances idempotentes (cf. select_update_channel)
# de CETTE CLI uniquement — le backend a sa propre source de vérité
# (réglage `update_channel` en base), non couplée à ce fichier.
mkdir -p "${CONFIG_DIR}" 2>/dev/null || true
write_file "${CONFIG_DIR}/update-channel" <<< "${UPDATE_CHANNEL}"

if [[ -d "${REPO_DIR}/.git" ]]; then
    # --force : les canaux Bêta et Canary reposent chacun sur un tag UNIQUE
    # et mobile ("beta"/"canary", un seul fichier de release par canal sur
    # GitHub plutôt qu'un tag par itération) — sans --force, un `git fetch`
    # classique refuse de mettre à jour un tag local si le tag distant a
    # bougé depuis le dernier fetch.
    run git -C "${REPO_DIR}" fetch --tags --force
    if [[ "${UPDATE_CHANNEL}" == "beta" || "${UPDATE_CHANNEL}" == "canary" ]]; then
        # Tag fixe, pas de recherche : la CI republie toujours sous ce même
        # nom (cf. .github/workflows/ci.yml, jobs release-beta/release-canary).
        # Peut ne pas exister encore (aucune release jamais publiée sur ce
        # canal) — vérifié juste après, pas de recherche à faire ici
        # contrairement à la branche stable.
        if git -C "${REPO_DIR}" rev-parse --verify -q "refs/tags/${UPDATE_CHANNEL}" >/dev/null; then
            TARGET_TAG="${UPDATE_CHANNEL}"
        else
            TARGET_TAG=""
        fi
    else
        # Dernier tag Vx.y.z, en excluant tout tag qui ne suit pas cette
        # forme stricte (garde-fou si un tag non standard existe).
        TARGET_TAG="$(git -C "${REPO_DIR}" tag --list 'V*' --sort=-v:refname 2>/dev/null | grep -E '^V[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)"
    fi
    if [[ -n "${TARGET_TAG:-}" ]]; then
        CURRENT_TAG="$(git -C "${REPO_DIR}" describe --tags --exact-match 2>/dev/null || true)"
        if [[ "${CURRENT_TAG}" != "${TARGET_TAG}" ]]; then
            log "Bascule sur ${TARGET_TAG} (canal ${UPDATE_CHANNEL})"
            run git -C "${REPO_DIR}" checkout "${TARGET_TAG}"
            # Le checkout a pu remplacer ce fichier par une autre version de
            # l'installateur (autres étapes, autres correctifs) : on repart de
            # la bonne, une seule fois (garde BOBINE_REEXEC). Les flux sont
            # rendus au terminal d'origine pour ne pas empiler deux tee.
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

# ---------------------------------------------------------------------------
step packages "Paquets système (apt)"
# ---------------------------------------------------------------------------
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
    # ni alsa-utils (amixer/aplay/alsactl) ni PipeWire/WirePlumber n'étaient
    # jamais installés par ce script alors que l'étape "audio" plus bas
    # écrit déjà une configuration WirePlumber dédiée
    # (/etc/wireplumber/wireplumber.conf.d/51-fix-jack-autoport.conf) et que
    # kiosk-xinitrc/bobine-audio-mute.sh appellent `amixer`/`pactl` sur
    # chaque carte détectée — sur un Debian minimal (netinst, sans tâche
    # bureau), AUCUN de ces binaires n'existe, et toutes ces commandes
    # échouaient silencieusement (`|| true`/`2>/dev/null` partout) : le
    # démute, le 100% matériel de référence et la coupure hors session ne
    # s'appliquaient jamais, Chromium retombant sur ALSA direct — ce qui ne
    # fonctionnait que par chance, tant qu'aucune autre application ne
    # prenait la carte son en même temps.
    ok "paquets système de base installés"

    # ----------------------------------------------------------------------
    # Détection matérielle DYNAMIQUE (GPU/CPU/firmware) : on adapte les paquets
    # au matériel RÉEL au lieu d'un Intel figé — la cible varie (Intel, AMD/
    # Ryzen, éventuellement NVIDIA). lspci/lscpu font partie de la base Debian.
    # ----------------------------------------------------------------------
    GPU_LINES="$(lspci -nn 2>/dev/null | grep -Ei 'VGA compatible controller|3D controller|Display controller' || true)"
    HAS_INTEL_GPU=false; HAS_AMD_GPU=false; HAS_NVIDIA_GPU=false
    grep -qiE '\[8086:' <<<"$GPU_LINES" && HAS_INTEL_GPU=true
    grep -qiE '\[1002:' <<<"$GPU_LINES" && HAS_AMD_GPU=true
    grep -qiE '\[10de:' <<<"$GPU_LINES" && HAS_NVIDIA_GPU=true
    CPU_VENDOR="$(LC_ALL=C lscpu 2>/dev/null | awk -F: '/Vendor ID/{gsub(/^[ \t]+/,"",$2);print $2; exit}')"
    ok "matériel détecté — GPU: Intel=$HAS_INTEL_GPU AMD=$HAS_AMD_GPU NVIDIA=$HAS_NVIDIA_GPU | CPU=${CPU_VENDOR:-inconnu}"

    # Les pilotes/firmwares non libres exigent les composants non-free* : on les
    # active AVANT si du matériel en a besoin, puis on rafraîchit apt.
    if $HAS_INTEL_GPU || $HAS_AMD_GPU || $HAS_NVIDIA_GPU; then
        if ! $DRY_RUN && ensure_apt_components; then
            run apt-get "${APT_OPTS[@]}" update -qq || true
        fi
    fi

    # Code QR de l'écran final (ouvrir l'admin depuis un téléphone) : confort
    # pur, jamais bloquant.
    command -v qrencode >/dev/null 2>&1 || apt_optional qrencode || true

    # Microcode CPU (stabilité/sécurité) selon le vendeur détecté.
    case "$CPU_VENDOR" in
        *AuthenticAMD*|*AMD*)     apt_optional amd64-microcode ;;
        *GenuineIntel*|*Intel*)   apt_optional intel-microcode ;;
    esac

    # Pilote VA-API (décodage vidéo matériel) selon le GPU détecté.
    if $HAS_INTEL_GPU; then
        apt_optional intel-media-va-driver-non-free || apt_optional intel-media-va-driver || apt_optional i965-va-driver
    fi
    if $HAS_AMD_GPU; then
        # radeonsi (Mesa) fournit le VA-API des GPU/APU AMD (Ryzen inclus).
        apt_optional mesa-va-drivers
        apt_optional firmware-amd-graphics
    fi
    if $HAS_NVIDIA_GPU && ! $HAS_INTEL_GPU && ! $HAS_AMD_GPU; then
        warn "GPU NVIDIA seul détecté : pas de pilote propriétaire installé (hors périmètre v1)."
        warn "Le décodage vidéo se fera en logiciel — surveiller la charge CPU sur l'écran réseau."
    fi

    # Firmware générique souvent nécessaire sur une base minimale (Wi-Fi/divers).
    apt_optional firmware-linux-free
    apt_optional firmware-misc-nonfree
    if ip -o link 2>/dev/null | grep -qiE ': wl'; then
        log "Interface Wi-Fi détectée : firmware sans fil"
        apt_optional firmware-iwlwifi
        apt_optional firmware-realtek
        apt_optional firmware-atheros
    fi

    # Node.js (build du frontend Next.js en export statique) : la version des
    # dépôts Debian est souvent trop ancienne, on installe donc une LTS actuelle
    # via NodeSource si besoin.
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

# ---------------------------------------------------------------------------
step gpu-access "Accès GPU (groupes render/video) & Xwrapper"
# ---------------------------------------------------------------------------
if $NO_KIOSK; then
    step_skip "--no-kiosk"
else
    run usermod -aG render,video "${TARGET_USER}"
    ok "${TARGET_USER} ajouté aux groupes render/video"
    # Onglet Périphériques : BlueZ n'autorise l'accès D-Bus qu'aux membres du groupe « bluetooth »
    # (le groupe n'existe que si le paquet bluez est installé : sans effet sinon).
    if getent group bluetooth >/dev/null 2>&1; then
        run usermod -aG bluetooth "${TARGET_USER}"
        ok "${TARGET_USER} ajouté au groupe bluetooth"
    fi

    # Autorise Xorg à démarrer depuis une session systemd (pas une console
    # physique classique) : nécessaire car le kiosk est lancé par un service,
    # pas un login interactif standard.
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

# ---------------------------------------------------------------------------
step python-env "Environnement Python & dépendances backend"
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
step frontend-build "Build du frontend Next.js"
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
step config "Configuration de production"
# ---------------------------------------------------------------------------
log "Écriture de ${CONFIG_FILE}"
run mkdir -p "${CONFIG_DIR}"
# Tous les dossiers média sous un unique arbre ${REPO_DIR}/data : avant ce correctif, seuls videos/watched/
# thumbnails étaient créés/déclarés, et audio/fonds/logs retombaient sur les
# défauts relatifs à backend/ → données éclatées sur deux arbres.
run mkdir -p \
    "${REPO_DIR}/data/videos" "${REPO_DIR}/data/watched" "${REPO_DIR}/data/thumbnails" \
    "${REPO_DIR}/data/backgrounds" "${REPO_DIR}/data/backgrounds_watched" \
    "${REPO_DIR}/data/audio" "${REPO_DIR}/data/audio_watched" \
    "${REPO_DIR}/data/radio" "${REPO_DIR}/data/radio_covers" \
    "${REPO_DIR}/data/radio_announcements" "${REPO_DIR}/data/radio_watched" \
    "${REPO_DIR}/data/logs"
run chown -R "${TARGET_USER}:${TARGET_USER}" "${REPO_DIR}/data"

write_file "${CONFIG_FILE}" <<EOF
# Configuration de production Bobine — générée par install.sh le $(date -Idate).
# Modifiable à la main ; relance 'sudo systemctl restart bobine-backend'
# après toute modification pour l'appliquer.

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
# Module Radio : sous-système musical
# indépendant, dossiers séparés des cours audio coach.
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

# Convergence des installations antérieures : jusqu'ici audio/fonds/logs pouvaient résider sous backend/data. On
# le signale et on oriente vers le script de migration dédié (opt-in, sauvegarde
# la base avant toute réécriture, à lancer backend arrêté) plutôt que de
# relocaliser automatiquement des données de production en plein install.
if [[ -d "${REPO_DIR}/backend/data" ]]; then
    warn "Données héritées détectées dans ${REPO_DIR}/backend/data (ancien emplacement)."
    warn "Pour les unifier sous ${REPO_DIR}/data, arrête le backend puis lance :"
    warn "  ${VENV_DIR}/bin/python ${REPO_DIR}/scripts/migrate_unify_data_dirs.py --dry-run"
    warn "puis à nouveau sans --dry-run une fois le plan vérifié."
fi
step_done

# ---------------------------------------------------------------------------
step cli-tool "Script de contrôle CLI 'bobine'"
# ---------------------------------------------------------------------------
write_file /usr/local/bin/bobine <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SERVICES=(bobine-backend.service bobine-kiosk.service)

case "${1:-}" in
    start)   sudo systemctl start "${SERVICES[@]}" ;;
    stop)    sudo systemctl stop "${SERVICES[@]}" ;;
    restart) sudo systemctl restart "${SERVICES[@]}" ;;
    status)  systemctl status "${SERVICES[@]}" --no-pager ;;
    logs)    journalctl -u bobine-backend -u bobine-kiosk -f ;;
    *)
        echo "Usage: bobine {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
EOF
run chmod +x /usr/local/bin/bobine
ok "commande 'bobine' installée"

# ---------------------------------------------------------------------------
step uninstaller "Désinstalleur détaché (bouton « Désinstaller » de l'UI)"
# ---------------------------------------------------------------------------
# Enveloppe lancée en root (règle sudoers dédiée ci-dessous) par le backend
# quand l'utilisateur confirme la désinstallation depuis Paramètres. systemd-run
# détache l'opération dans une unité transitoire : sans cela, l'arrêt du service
# backend (déclenché par --uninstall) tuerait le script lui-même, qui tourne
# dans le même cgroup. La désinstallation elle-même reste celle, déjà testée,
# de --uninstall --purge --purge-data (services + config + app + données, sans
# toucher aux paquets apt partagés).
write_file /usr/local/sbin/bobine-uninstall <<EOF
#!/usr/bin/env bash
exec systemd-run --collect --unit=olmc-uninstall --description="Bobine uninstall" ${REPO_DIR}/install.sh --uninstall --purge --purge-data -y
EOF
run chmod +x /usr/local/sbin/bobine-uninstall
ok "désinstalleur '/usr/local/sbin/bobine-uninstall' installé"
step_done

# ---------------------------------------------------------------------------
step storage-access "Autorisation des supports amovibles"
run sh "${REPO_DIR}/packaging/storage/configure-storage-access" configure "${TARGET_USER}"
step_done

step backend-service "Service systemd — backend FastAPI"
# ---------------------------------------------------------------------------
write_file /etc/systemd/system/bobine-backend.service <<EOF
[Unit]
Description=Bobine - Backend FastAPI
After=network.target

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_USER}
WorkingDirectory=${BACKEND_DIR}
# Même point d'entrée que les applications de bureau (résolution du port partagée). Le port est
# déterministe sur l'appliance : BOBINE_PORT_STRICT=1 interdit le repli sur un autre port (la
# redirection 80 -> ${SERVICE_PORT} et le pare-feu supposent ce port) ; si ${SERVICE_PORT} est occupé, le
# démarrage échoue avec un message clair dans le journal (journalctl -u bobine-backend).
Environment=BOBINE_PORT=${SERVICE_PORT}
Environment=BOBINE_PORT_STRICT=1
ExecStart=${VENV_DIR}/bin/python ${BACKEND_DIR}/run_backend.py
Restart=always
RestartSec=2
# Reprise après coupure électrique : démarrage automatique au boot via
# [Install] ci-dessous + Restart=always pour toute panne en cours de vie.

[Install]
WantedBy=multi-user.target
EOF
ok "bobine-backend.service écrit"
step_done

# ---------------------------------------------------------------------------
step kiosk "Kiosk Chromium (écran cinéma câblé)"
# ---------------------------------------------------------------------------
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

    # En-tête généré (valeurs résolues à l'installation), suivi du corps statique.
    write_file "${CONFIG_DIR}/kiosk-xinitrc" <<EOF
#!/bin/sh
# Généré par install.sh — lancé par Xorg au démarrage de la session kiosk.
CHROMIUM_BIN="${CHROMIUM_BIN}"
KIOSK_URL="${KIOSK_URL}"
EOF
    append_file "${CONFIG_DIR}/kiosk-xinitrc" <<'EOF'

# Pas de mise en veille ni d'écran noir sur l'écran cinéma.
xset s off
xset -dpms
xset s noblank

# Masque le curseur de souris (pas d'interaction locale attendue).
if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.1 -root &
fi

# --- Configuration de l'affichage (correctif "écran réduit au lancement") ---
# Deux causes observées sur le Wyse : (1) une sortie fantôme configurée par
# Xorg à côté de la vraie (bureau étendu 3840x1080 dont l'écran ne montre
# qu'une moitié), (2) aucun window manager ne tourne dans cette session, donc
# la demande de plein écran de Chromium (--kiosk) n'est honorée par personne
# et la fenêtre reste à sa taille par défaut. On force donc ici LA sortie
# réellement connectée à son mode préféré en 0x0, on éteint toutes les
# autres, puis on passe à Chromium une géométrie explicite.
# L'EDID d'un projecteur peut mettre quelques secondes à être lisible au
# démarrage à froid : on réessaie avant de se rabattre sur l'état courant.
OUTPUT=""
for _ in $(seq 1 15); do
    # Sortie retenue : une sortie EXTERNE (HDMI/DP...) de préférence à une
    # dalle interne (eDP/LVDS/DSI) quand les deux sont connectées (mini-PC
    # portable branché sur un projecteur), sinon la première connectée. Une
    # reconfiguration à chaud est déclenchée par bobine-display-hotplug
    # (règle udev DRM) qui redémarre cette session.
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

# Géométrie réelle de l'écran après configuration (repli 1920x1080 si illisible).
SCREEN_SIZE=$(xrandr --query | awk -F'[ ,]+' '/current/{print $8"x"$10; exit}')
case "${SCREEN_SIZE}" in
    [0-9]*x[0-9]*) ;;
    *) SCREEN_SIZE="1920x1080" ;;
esac
SCREEN_W=${SCREEN_SIZE%x*}
SCREEN_H=${SCREEN_SIZE#*x}

# Attend que le backend réponde avant de lancer Chromium : sinon la page
# d'erreur "connexion refusée" reste affichée jusqu'à intervention manuelle.
for _ in $(seq 1 60); do
    curl -fsS -o /dev/null "${KIOSK_URL%/kiosk}/api/health" && break
    sleep 1
done

# Sécurité audio : WirePlumber/ACP
# réinitialise certains registres bruts du codec (dont 'Auto-Mute Mode') à
# leur valeur par défaut ('Disabled') à chaque activation de profil, ce qui
# annule silencieusement 'alsactl store' au boot suivant — reconstaté ici
# après plusieurs redémarrages. On le réapplique donc à chaque lancement du
# kiosk (après l'attente ci-dessus, WirePlumber a largement eu le temps de
# démarrer) plutôt que de compter sur la persistance ALSA seule.
# Démute explicite : bobine-audio-guard.service coupe
# Master/Speaker par défaut hors session kiosk, c'est ici qu'on les rouvre
# une fois prêt.
#
# Dynamique et non figée sur "carte 0" : la sortie câblée peut être une carte
# différente selon le boîtier (Wyse, mini-PC...), et un même codec expose
# souvent plusieurs sorties analogiques simultanées (Speaker = interne/arrière,
# Headphone/Headphone+LO = prise avant, Front/Surround = autres canaux) qui
# partagent le même flux PCM plutôt que de s'exclure — sauf que le registre
# 'Auto-Mute Mode' du codec, LUI, coupe automatiquement les autres sorties dès
# qu'un jack est détecté branché (cause du bug "une seule prise fonctionne").
# On le désactive donc explicitement, puis on démute/monte à 100% CHAQUE
# contrôle de lecture découvert sur CHAQUE carte, plutôt qu'une liste figée de
# noms — pour que toutes les prises câblées restent actives en même temps,
# quel que soit le matériel.
for BOBINE_CARD in $(awk -F'[][]' '/^ *[0-9]+ \[/{print $2}' /proc/asound/cards 2>/dev/null | sed 's/[[:space:]]*$//'); do
    amixer -c "${BOBINE_CARD}" sset 'Auto-Mute Mode' 'Disabled' >/dev/null 2>&1 || true
    # Volume explicite plutôt qu'un simple "unmute" (le cycle mute/unmute
    # pouvait laisser le volume matériel à 0% tout en étant démuté — son coupé
    # de façon non-évidente). 100% (0dB, niveau ligne de référence) sur TOUS
    # les chemins de sortie : le Wyse alimente une table de mixage, c'est ELLE
    # qui atténue — un niveau source réduit obligeait à pousser le gain de la
    # table au maximum, ce qui est pire (bruit de fond amplifié, aucune
    # marge). Le réglage de volume "utilisateur" reste disponible via les
    # boutons de l'interface (volume logiciel appliqué au flux par le kiosk),
    # indépendant de ces niveaux matériels de référence.
    amixer -c "${BOBINE_CARD}" scontrols 2>/dev/null | sed -n "s/^Simple mixer control '\([^']*\)'.*/\1/p" | sort -u | while IFS= read -r BOBINE_CTRL; do
        case "${BOBINE_CTRL}" in
            # IEC958*/Beep/Loopback ajoutés : un contrôle numérique S/PDIF ou de rebouclage
            # démuté à 100% par erreur peut activer une sortie parasite sur
            # certains codecs, jamais souhaitée sur ce déploiement.
            *[Mm]ic*|*Boost|Capture|"Input Source"|"Auto-Mute Mode"|IEC958*|Beep|Loopback) continue ;;
        esac
        amixer -c "${BOBINE_CARD}" sset "${BOBINE_CTRL}" 100% unmute >/dev/null 2>&1 || true
    done
    # Chemin micro fermé : la prise avant est une prise combo casque/micro (TRRS) — le
    # codec y détectait un "Headset Mic" fantôme et polarisait le contact
    # micro avec Capture ET Headset Mic Boost à fond (+60dB cumulés). Un câble
    # stéréo TRS classique branché là court-circuite ce contact polarisé vers
    # la masse audio -> bruit électrique continu injecté dans l'ampli. Aucun
    # micro n'est utilisé sur ce déploiement : gains à zéro, capture coupée,
    # et source d'entrée déplacée sur le micro ARRIÈRE (rien d'y branché) pour
    # éloigner la polarisation du jack avant utilisé en sortie. Contrôles
    # optionnels selon le codec (mini-PC sans prise micro dédiée) : chacun est
    # tenté isolément, sans erreur si absent.
    amixer -c "${BOBINE_CARD}" sset 'Capture' 0% nocap >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" sset 'Capture',1 0% nocap >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" sset 'Headset Mic Boost' 0 >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" sset 'Rear Mic Boost' 0 >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" cset name='Input Source' 'Rear Mic' >/dev/null 2>&1 || true
    amixer -c "${BOBINE_CARD}" cset name='Input Source',index=1 'Rear Mic' >/dev/null 2>&1 || true
done
# Volume logiciel PipeWire aussi à 100% sur TOUS les sinks (pas seulement le
# sink par défaut) : c'est le canal que pilotent les boutons de volume de
# l'interface — un plafond logiciel bas ici aurait le même défaut que le
# plafond matériel corrigé ci-dessus, et un boîtier avec plusieurs cartes son
# expose potentiellement plusieurs sinks WirePlumber.
pactl list short sinks 2>/dev/null | cut -f1 | while IFS= read -r BOBINE_SINK; do
    pactl set-sink-volume "${BOBINE_SINK}" 100% >/dev/null 2>&1 || true
done

# Profil Chromium dédié et jetable, purgé à chaque lancement du kiosk :
# supprime toutes les données temporaires de chargement (cache d'une ancienne
# version du frontend après mise à jour, état de session "crashed", service
# workers). Tout est resservi par le backend local, la purge est sans coût.
KIOSK_PROFILE="/var/tmp/bobine-kiosk-profile"
rm -rf "${KIOSK_PROFILE}"

# Flags VAAPI validés à l'installation — à re-vérifier après install via
# chrome://gpu et 'intel_gpu_top' (cf. rappel affiché en fin de script).
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
    --check-for-update-interval=31536000
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
# Memorise la topologie des ecrans au demarrage de la session (prefixe + = en
# root) : bobine-display-hotplug ne redemarre le kiosque que si elle CHANGE.
ExecStartPre=+${REPO_DIR}/scripts/bobine-display-hotplug.sh --record
ExecStart=/usr/bin/xinit ${CONFIG_DIR}/kiosk-xinitrc -- :0 vt1 -nolisten tcp

[Install]
WantedBy=multi-user.target
EOF
    ok "bobine-kiosk.service + kiosk-xinitrc écrits"

    # Branchement/débranchement d'un projecteur ou d'une TV à chaud : règle udev DRM -> unité oneshot -> redémarrage du kiosque si la
    # liste des sorties connectées a changé (cf. scripts/bobine-display-hotplug.sh).
    run chmod +x "${REPO_DIR}/scripts/bobine-display-hotplug.sh"
    write_file /etc/systemd/system/bobine-display-hotplug.service <<EOF
[Unit]
Description=Bobine - Reconfiguration du kiosque au branchement d'un ecran
After=bobine-kiosk.service
# Les evenements HPD arrivent en rafale : le script s'anti-rebondit lui-meme.
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=${REPO_DIR}/scripts/bobine-display-hotplug.sh
EOF
    write_file /etc/udev/rules.d/90-bobine-display.rules <<'EOF'
# Bobine : evenement de branchement/debranchement d'un ecran (HPD DRM).
ACTION=="change", SUBSYSTEM=="drm", ENV{HOTPLUG}=="1", TAG+="systemd", ENV{SYSTEMD_WANTS}+="bobine-display-hotplug.service"
EOF
    ok "hotplug des écrans (udev DRM + bobine-display-hotplug) écrit"
    step_done
fi

# ---------------------------------------------------------------------------
step audio "Audio (auto-port, anti-sifflement, garde-fou hors session)"
# ---------------------------------------------------------------------------
if $NO_KIOSK; then
    step_skip "--no-kiosk"
else
    # WirePlumber désactive api.acp.auto-port/auto-profile par défaut pour
    # toutes les cartes ALSA, ce qui fige la sortie active sur le port choisi
    # au démarrage quel que soit le jack réellement branché (cause du bug
    # "une seule prise fonctionne" + bruits stridents sur sortie DAC non
    # pilotée). On restaure ici la commutation automatique de prise jack.
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

    # Mise en veille du codec HDA désactivée (anti-sifflement) : avec
    # power_save=1 (défaut Debian), le codec Realtek se coupe après ~1s
    # d'inactivité et se rallume à la demande — chaque cycle laisse la sortie
    # analogique flotter puis produit un pop, source classique de sifflement
    # continu sur un ampli externe. Constaté sur ce Wyse : 8x plus de temps
    # éteint qu'allumé en usage kiosk normal. Coût : ~0,5W de plus, sans objet
    # sur une machine branchée secteur en continu.
    write_file /etc/modprobe.d/bobine-audio.conf <<'EOF'
options snd-hda-intel power_save=0 power_save_controller=N
EOF
    # Application immédiate sans attendre le prochain reboot. Réf.
    # Le chemin PCI `0000:00:0e.0` ci-dessus était figé sur celui du Wyse
    # 5070 précis — sans effet sur tout autre modèle/chipset (AMD, autre
    # Intel) et sur les DAC USB (snd_usb_audio, qui n'a pas de paramètre
    # power_save propre mais expose le même mécanisme générique
    # `power/control` sous sysfs). Boucle sur TOUTES les cartes son
    # réellement présentes plutôt qu'un chemin unique — couvre HDA et USB
    # de la même façon, sans avoir besoin de distinguer les deux.
    if ! $DRY_RUN; then
        echo 0 > /sys/module/snd_hda_intel/parameters/power_save 2>/dev/null || true
        for BOBINE_PC in /sys/class/sound/card*/device/power/control; do
            [[ -e "${BOBINE_PC}" ]] && echo on > "${BOBINE_PC}" 2>/dev/null || true
        done
    fi
    ok "mise en veille du codec audio désactivée (HDA et USB)"

    # Si un powertop.service ("powertop --auto-tune") existe sur la machine,
    # il RÉACTIVE power_save=1 à chaque boot APRÈS le chargement du module,
    # annulant silencieusement le réglage modprobe ci-dessus. Drop-in qui
    # restaure le réglage anti-bruit juste après son passage, sans toucher à
    # ses autres optimisations.
    if [[ -f /etc/systemd/system/powertop.service ]]; then
        run mkdir -p /etc/systemd/system/powertop.service.d
        write_file /etc/systemd/system/powertop.service.d/10-audio-nopowersave.conf <<'EOF'
[Service]
ExecStartPost=/bin/sh -c 'echo 0 > /sys/module/snd_hda_intel/parameters/power_save'
ExecStartPost=/bin/sh -c 'for pc in /sys/class/sound/card*/device/power/control; do [ -e "$pc" ] && echo on > "$pc"; done; true'
EOF
        ok "garde-fou powertop installé"
    fi

    # Coupe le son hors session kiosk : ni le correctif Auto-Mute Mode
    # ci-dessus (appliqué seulement dans kiosk-xinitrc, tard dans le boot,
    # une fois le backend joignable) ni 'alsactl store' seul ne couvrent la
    # fenêtre AVANT que le kiosk démarre ni celle APRÈS son arrêt
    # (redémarrage/extinction) — exactement la fenêtre où une sortie DAC non
    # pilotée peut hurler. Ce service coupe TOUTES les sorties de lecture
    # découvertes, sur TOUTES les cartes ALSA (script dédié, pas une liste de
    # noms figée sur "carte 0" — même logique dynamique que kiosk-xinitrc, qui
    # gère plusieurs sorties câblées simultanées) au tout début du boot (bien
    # avant le kiosk) et les recoupe explicitement à l'arrêt ; kiosk-xinitrc
    # les rouvre une fois réellement prêt à jouer du son.
    write_file /usr/local/bin/bobine-audio-mute.sh <<'EOF'
#!/bin/sh
CARDS=$(awk -F'[][]' '/^ *[0-9]+ \[/{print $2}' /proc/asound/cards 2>/dev/null | sed 's/[[:space:]]*$//')
# Carte pas encore énumérée par le noyau au tout début du boot (cf.
# Restart=on-failure du service appelant) : on échoue explicitement pour
# déclencher une nouvelle tentative plutôt que de "réussir" sans rien couper.
[ -z "${CARDS}" ] && exit 1
for CARD in ${CARDS}; do
    amixer -c "${CARD}" scontrols 2>/dev/null | sed -n "s/^Simple mixer control '\([^']*\)'.*/\1/p" | sort -u | while IFS= read -r CTRL; do
        case "${CTRL}" in
            # IEC958*/Beep/Loopback ajoutés : un contrôle numérique S/PDIF ou de rebouclage
            # démuté à 100% par erreur peut activer une sortie parasite sur
            # certains codecs, jamais souhaitée sur ce déploiement.
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
# La carte ALSA (module noyau snd_hda_intel, énumération PCI) n'est pas
# forcément prête au moment où ce service démarre malgré WantedBy=multi-user
# — constaté : "amixer: Invalid card number '0'" au premier boot après
# installation. Pas de dépendance systemd fiable à 100% sur la disponibilité
# d'une carte son précise (systemd-udev-settle est déconseillé/plus lent) :
# on retente donc simplement toutes les secondes plutôt que de dépendre d'un
# ordonnancement exact, la carte apparaît toujours en quelques secondes.
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

# ---------------------------------------------------------------------------
step sudoers "Autorisation sudo restreinte (bouton de réinitialisation)"
# ---------------------------------------------------------------------------
log "Autorisation sudo restreinte pour le redémarrage des services depuis l'UI"
if $NO_KIOSK; then
    SUDOERS_UNITS="/usr/bin/systemctl restart bobine-backend.service"
else
    SUDOERS_UNITS="/usr/bin/systemctl restart bobine-backend.service, /usr/bin/systemctl restart bobine-kiosk.service"
fi
# Enveloppe de désinstallation (bouton « Désinstaller » de l'UI) : commande
# unique, sans argument, qui détache le --uninstall via systemd-run.
SUDOERS_UNITS="${SUDOERS_UNITS}, /usr/local/sbin/bobine-uninstall"
write_file /etc/sudoers.d/bobine <<EOF
# Autorise UNIQUEMENT ces commandes précises, sans mot de passe :
#   - le redémarrage des unités (bouton de réinitialisation des paramètres) ;
#   - l'enveloppe de désinstallation /usr/local/sbin/bobine-uninstall
#     (bouton « Désinstaller », remise à zéro complète).
# Ne JAMAIS élargir à d'autres commandes ni remplacer par NOPASSWD: ALL.
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

# ---------------------------------------------------------------------------
step ntp "Synchronisation NTP"
# ---------------------------------------------------------------------------
# Défense en profondeur derrière le correctif applicatif (/api/time + offset
# côté kiosk) : sans NTP, l'horloge RTC du Wyse peut dériver indépendamment
# de toute correction logicielle côté navigateur.
if command -v timedatectl >/dev/null 2>&1; then
    run timedatectl set-ntp true
    ok "systemd-timesyncd activé"
else
    warn "timedatectl introuvable — vérifier manuellement la synchronisation NTP du système"
fi
step_done

# ---------------------------------------------------------------------------
step mdns-redirect "URL locale (mDNS) & redirection du port 80"
# ---------------------------------------------------------------------------
# - avahi (mDNS) publie "bobine.local" sur le LAN sans toucher au
#   hostname de la machine ;
# - une règle nftables redirige le port 80 entrant vers le port applicatif,
#   pour une URL sans numéro de port depuis téléphone/PC. L'URL historique
#   http://<IP>:8000 reste fonctionnelle.
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
    # IPv6 désactivé côté avahi : le paquet Debian publie par défaut
    # use-ipv6=yes, donc une adresse AAAA globale en plus de l'IPv4 — mais
    # rien dans la pile (redirection nftables port 80, bind uvicorn
    # "0.0.0.0") ne gère l'IPv6 de bout en bout. Un client qui préfère IPv6
    # (comportement courant des navigateurs) se connecte alors à un port
    # fermé -> refus immédiat, alors que l'IPv4 fonctionne. Plus simple de ne
    # publier que l'IPv4 que d'ajouter un vrai support IPv6 pour un usage LAN.
    if grep -qE '^#?use-ipv6=' "${AVAHI_CONF}"; then
        sed -i 's/^#\?use-ipv6=.*/use-ipv6=no/' "${AVAHI_CONF}"
    else
        sed -i '/^\[server\]/a use-ipv6=no' "${AVAHI_CONF}"
    fi
fi
# Le service peut être masqué sur une installation Debian durcie : démasqué
# explicitement (unité + socket) avant activation. Échec toléré : le mDNS est
# un confort, l'accès par http://<IP>:8000 reste toujours valable.
run systemctl unmask avahi-daemon.service avahi-daemon.socket >/dev/null 2>&1 || true

# Cas traité : « bobine.local » injoignable après un redémarrage complet, alors que
# `systemctl restart avahi-daemon` seul fonctionnait. L'unité avahi-daemon
# livrée par Debian ne dépend QUE de sysinit.target/basic.target, pas de
# network-online.target — rien sur cette machine ne tire cette cible non
# plus (NetworkManager-wait-online.service est activable mais jamais
# sollicité). Au premier restart après install, l'interface avait déjà son
# bail DHCP depuis longtemps donc ça passait inaperçu ; à un boot à froid,
# avahi peut démarrer avant que l'interface réseau ait une adresse. avahi
# republie normalement dès qu'il détecte le changement d'interface (netlink),
# mais ce filet dépendait jusqu'ici du hasard du timing plutôt que d'être
# garanti — on le rend explicite.
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
    warn "L'accès par adresse IP (http://<IP-du-Wyse>:8000) reste fonctionnel."
else
    ok "avahi-daemon actif"
fi

log "Redirection du port 80 vers ${SERVICE_PORT} (nftables)"
write_file "${CONFIG_DIR}/redirect.nft" <<EOF
# Généré par install.sh — accès sans numéro de port (http://bobine.local).
# Le triplet create/delete/create rend le rechargement idempotent.
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
step_done

# ---------------------------------------------------------------------------
step watchdog "Chien de garde de santé (watchdog)"
# ---------------------------------------------------------------------------
# Redémarrage AUTOMATIQUE d'un composant mort en consommant /api/health (base
# SQLite, kiosque Chromium). Complète `Restart=always` de systemd, qui ne
# couvre que la mort du *processus*, pas les défaillances *logiques* (backend
# vivant mais base verrouillée, Chromium gelé…). Piloté par un TIMER systemd
# (pas de process résident). Distinct du garde AUDIO (`bobine-audio-guard`, un
# oneshot qui coupe le son hors session kiosk) : rôles séparés.
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
# Laisse le systeme finir de booter avant la premiere passe (evite de lutter
# contre le demarrage normal des services), puis une passe toutes les 30 s.
OnBootSec=90s
OnUnitActiveSec=30s
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
ok "chien de garde santé (watchdog) écrit"
step_done

# ---------------------------------------------------------------------------
step tuning "Optimisations système (gouverneur CPU, journal)"
# ---------------------------------------------------------------------------
# Deux optimisations à faible risque, appliquées dès l'installation plutôt que
# laissées aux valeurs par défaut Debian (pensées pour un poste de bureau
# économe en énergie, pas une appliance branchée secteur en continu).
if $NO_KIOSK; then
    step_skip "--no-kiosk"
else
    # Gouverneur CPU "performance" : évite les changements de fréquence sous
    # charge variable (lecture vidéo + décodage/encodage ffmpeg concurrents)
    # qui peuvent introduire des micro-saccades — sans intérêt énergétique
    # ici, la machine reste branchée secteur en permanence (kiosque de
    # salle). Service oneshot plutôt qu'une simple commande ponctuelle :
    # certains noyaux réinitialisent le gouverneur par défaut à chaque
    # démarrage, un service WantedBy=multi-user.target le réapplique à
    # chaque boot sans dépendre d'un fichier de config spécifique au pilote
    # cpufreq présent (intel_pstate, acpi-cpufreq...).
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

    # Plafond du journal systemd : par défaut Debian autorise jusqu'à 10% du
    # disque pour /var/log/journal — sans limite explicite, une appliance
    # tournant 24/7 pendant des mois sur un stockage eMMC/SSD limité peut
    # voir son journal grossir sans borne raisonnable.
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

# ---------------------------------------------------------------------------
step activation "Activation des services & vérification de santé"
# ---------------------------------------------------------------------------
run systemctl daemon-reload
if ! $NO_KIOSK; then
    run systemctl enable bobine-audio-guard.service
    run systemctl restart bobine-audio-guard.service 2>/dev/null || run systemctl start bobine-audio-guard.service
fi
run systemctl enable bobine-backend.service
run systemctl restart bobine-backend.service 2>/dev/null || run systemctl start bobine-backend.service
# Chien de garde : actif dans tous les modes (surveille au moins le backend).
run systemctl enable bobine-watchdog.timer
run systemctl restart bobine-watchdog.timer 2>/dev/null || run systemctl start bobine-watchdog.timer
if ! $NO_KIOSK; then
    run systemctl enable bobine-kiosk.service
    run systemctl restart bobine-kiosk.service 2>/dev/null || run systemctl start bobine-kiosk.service
    # Prise en compte de la regle udev de hotplug des ecrans (sans reboot).
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

# ---------------------------------------------------------------------------
step capabilities "Vérification des capacités audio & vidéo"
# ---------------------------------------------------------------------------
# Jusqu'ici, rien ne
# vérifiait après coup que l'audio et le décodage matériel fonctionnent
# RÉELLEMENT — un déploiement pouvait être déclaré "terminé" avec un son
# muet ou un décodage logiciel, sans qu'aucun signal ne le distingue d'une
# installation saine avant de le découvrir en salle. Purement diagnostique :
# ne modifie rien, n'échoue jamais le script (avertissements seulement).
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

# ---------------------------------------------------------------------------
# Résumé final
# ---------------------------------------------------------------------------
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
box_line "  Contrôle   bobine {start|stop|restart|status|logs}"
box_line "  Diagnostic sudo ./${SCRIPT_NAME} --check"
if ! $NO_KIOSK && ! $DRY_RUN; then
    box_mid
    box_line "  Audio      $($AUDIO_OK && echo 'OK' || echo 'À VÉRIFIER — voir aplay -l')"
    box_line "  Vidéo (VA-API) $($VAAPI_OK && echo 'OK (matériel)' || echo 'décodage logiciel — voir vainfo')"
fi
box_bottom
echo

# Code QR : un scan et l'admin s'ouvre sur le téléphone du gérant.
if [[ -n "${LAN_IP:-}" ]] && ! $DRY_RUN && ! $QUIET && command -v qrencode >/dev/null 2>&1; then
    printf '  %s%s%s\n' "$BOLD" "$(t "Ouvrir l'admin depuis un téléphone :" "Open the admin from a phone:")" "$RESET"
    qrencode -t ANSIUTF8 -m 1 "http://${LAN_IP}" 2>/dev/null | sed 's/^/    /' || true
    echo
fi

# Fin de la séquence pilotable : l'assistant peut fermer sa barre à 100 % et
# afficher l'écran final (URL/QR). healthy reflète le contrôle /api/health.
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
