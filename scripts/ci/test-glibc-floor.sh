#!/usr/bin/env bash
# Test négatif du plancher glibc : le gestionnaire de paquets d'une distribution dont la glibc est inférieure à
# packaging/common/MIN_GLIBC doit REFUSER le paquet, et pour cette raison. Échoue si le paquet est accepté, ou refusé
# pour une autre raison (dépendance manquante, architecture) : un refus étranger ne prouverait rien.
#   deb : Debian 12 et Ubuntu 22.04, `apt-get install ./bobine.deb` doit citer « libc6 (>= <plancher>) » ;
#   rpm : AlmaLinux 9 (RHEL 9), `rpm -U --test bobine.rpm` doit citer « glibc >= <plancher> ». C'est le même contrôle de
#         dépendances que celui de dnf, sans les métadonnées des miroirs : sur les exécuteurs ARM64 de GitHub, dnf pouvait
#         rester bloqué près de trente minutes sur un miroir lent.
# Usage : test-glibc-floor.sh deb|rpm <fichier>   (Docker ou Podman ; les images suivent l'architecture de la machine)
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
family="${1:?deb ou rpm}"; file="${2:?fichier du paquet}"
[ -f "$file" ] || { echo "Erreur: $file introuvable." >&2; exit 2; }
. "$root/scripts/ci/container-images.sh"
floor="$(tr -d '[:space:]' < "$root/packaging/common/MIN_GLIBC")"
engine="${CONTAINER_ENGINE:-docker}"

case "$family" in
    deb)
        images=("$DEBIAN12_IMAGE" "$UBUNTU2204_IMAGE")
        expected="libc6 (>= $floor)"
        install='apt-get update -qq >/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y "$1"'
        installed='dpkg-query -W bobine'
        ;;
    rpm)
        images=("$ALMA9_IMAGE")
        expected="glibc >= $floor"
        install='rpm -U --test "$1"'
        installed='rpm -q bobine'
        ;;
    *) echo "Erreur: famille inconnue ($family)." >&2; exit 2 ;;
esac

inner='
echo "Image : $(. /etc/os-release; echo "$PRETTY_NAME"), $(ldd --version | head -n1), architecture $(uname -m)"
if '"$install"' > /tmp/install.out 2>&1; then
    cat /tmp/install.out
    echo; echo "ERREUR: le paquet a été installé alors que la glibc de cette image est inférieure à $3." >&2
    exit 1
fi
cat /tmp/install.out
if ! grep -qF -- "$2" /tmp/install.out; then
    echo "ERREUR: refus pour une autre raison : « $2 » est absent de la sortie." >&2
    exit 1
fi
if '"$installed"' >/dev/null 2>&1; then
    echo "ERREUR: le paquet est installé malgré le refus." >&2
    exit 1
fi
echo "Refus attendu : « $2 »."
'
status=0
for image in "${images[@]}"; do
    echo "=== $family sur $image ==="
    # Un miroir de distribution peut répondre vide ou se bloquer : trois essais bornés à dix minutes chacun, un vrai défaut
    # échoue les trois fois.
    ok=0
    for attempt in 1 2 3; do
        if timeout 600 "$engine" run --rm -v "$(cd "$(dirname "$file")" && pwd):/pkg:ro" "$image" \
            bash -c "$inner" -- "/pkg/$(basename "$file")" "$expected" "$floor"; then ok=1; break; fi
        echo "Essai $attempt/3 sans succès sur $image." >&2
    done
    [ "$ok" -eq 1 ] || status=1
done
exit "$status"
