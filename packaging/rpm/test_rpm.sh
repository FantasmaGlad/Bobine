#!/usr/bin/env bash
# Contrôles du paquet RPM, à lancer DANS un conteneur Fedora (root) :
#   rpm -qlp, rpmlint, installation réelle (dnf), présence des fichiers, lancement du backend installé, désinstallation.
# Usage : test_rpm.sh <fichier.rpm> [--no-install]
set -euo pipefail
RPM_FILE="${1:?fichier .rpm}"
INSTALL=1; [ "${2:-}" = "--no-install" ] && INSTALL=0

echo "=== rpm -qip / -qlp ==="
rpm -qip "${RPM_FILE}"
rpm -qlp "${RPM_FILE}"
echo "=== dépendances ==="
rpm -qp --requires "${RPM_FILE}"
rpm -qp --recommends "${RPM_FILE}"

echo "=== rpmlint ==="
dnf -q -y install rpmlint >/dev/null
# Filtres justifiés dans bobine.rpmlintrc ; toute autre erreur fait échouer le contrôle.
rpmlint --ignore-unused-rpmlintrc -r "$(dirname "${BASH_SOURCE[0]}")/bobine.rpmlintrc" "${RPM_FILE}" 

[ "${INSTALL}" = "1" ] || exit 0
echo "=== installation réelle ==="
dnf -y install "${RPM_FILE}"
test -x /usr/bin/bobine
test -x /usr/lib/bobine/BobineBackend
test -x /usr/lib/bobine/BobineTray
test -f /usr/share/applications/com.bobine.app.desktop
test -f /etc/xdg/autostart/com.bobine.app.desktop
test -f /usr/share/metainfo/com.bobine.app.metainfo.xml
test -f /usr/lib/systemd/user/bobine.service
test -f /usr/share/icons/hicolor/256x256/apps/bobine.png
test -f /usr/share/pixmaps/bobine.png
test -f /usr/lib/firewalld/services/bobine.xml
if [ -e /usr/lib/bobine/bobine-media ]; then test -x /usr/lib/bobine/bobine-media; fi
rpm -V bobine
desktop-file-validate /usr/share/applications/com.bobine.app.desktop
echo "=== lancement de l'application installée ==="
"$(dirname "${BASH_SOURCE[0]}")/../../scripts/ci/smoke-installed-backend.sh"
echo "=== réinstallation (mise à jour sur place) ==="
dnf -y reinstall "${RPM_FILE}"
echo "=== désinstallation ==="
dnf -y remove bobine
test ! -e /usr/lib/bobine
echo "RPM OK"
