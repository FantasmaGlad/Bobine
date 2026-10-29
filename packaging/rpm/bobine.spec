# Spécification RPM de Bobine (Fedora et dérivés ; compatibilité entreprise à valider séparément).
#
# Ce n'est PAS le .spec PyInstaller (packaging/linux/bobine.spec) : ici on EMBALLE
# l'arbre PyInstaller déjà construit (même binaire que le .deb), aucune compilation.
# Construit par packaging/rpm/build_rpm.sh, qui fournit les macros bobine_* et la
# source (arborescence FHS produite par packaging/common/stage_root.sh).

%global debug_package %{nil}
%global _build_id_links none
# Le bundle PyInstaller embarque ses propres bibliothèques : ni strip, ni scan des
# dépendances/fournitures internes, ni recompilation de bytecode Python.
%global __os_install_post %{nil}
%global __requires_exclude_from ^/usr/lib/bobine/.*$
%global __provides_exclude_from ^/usr/lib/bobine/.*$
%define _binary_payload w19.zstdio
%define _source_payload w19.zstdio
%define _binary_filedigest_algorithm 8

Name:           bobine
Version:        %{bobine_version}
Release:        %{bobine_release}
Summary:        Video and audio playout for gyms and fitness studios
License:        AGPL-3.0-or-later
URL:            https://bobine.fit
Source0:        bobine-root.tar
Source1:        bobine-firewalld.xml
AutoReqProv:    no

# ffmpeg complet : « ffmpeg » de RPM Fusion, ou « ffmpeg-free » (codecs limités) des
# dépôts Fedora. Dépendance exprimée par fichier pour accepter l'un ou l'autre.
Requires:       /usr/bin/ffmpeg
Requires:       /usr/bin/ffprobe
# Le bundle est construit sur une base glibc récente : refuser l'installation plutôt
# que de planter au lancement (valeur calculée au build, voir build_rpm.sh).
Recommends:     avahi
Recommends:     udisks2
Recommends:     smartmontools
Requires:       udisks2
Requires:       smartmontools
Requires:       exfatprogs
Requires:       e2fsprogs
Requires:       dosfstools
Requires:       ntfs-3g
Requires:       polkit
Recommends:     exfatprogs
Recommends:     polkit
Recommends:     gvfs
Recommends:     gvfs-mtp
Recommends:     gvfs-fuse
Suggests:       chromium
Suggests:       firewalld

%description
Bobine plays planned classes on the studio screen, offers a self-service
cinema kiosk and background radio, and is driven from a phone or a browser
on the local network. Everything runs on site: no subscription, no cloud.

Main features: wired HDMI output and an independent network screen kept in
sync; class schedule with one-off and recurring sessions, playlists, subtitles
and chapters; coach mode with a timer and animated backgrounds; background
radio with crossfade and voice announcements; mobile remote control and web
administration; backup, restore and factory reset.

Released under the GNU AGPL v3.0 or later.
Source code: https://github.com/FantasmaGlad/Bobine

%prep
# Rien à décompresser ici : la source est l'arborescence déjà assemblée.

%build
# Aucune compilation (arbre PyInstaller prêt).

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
tar -xf %{SOURCE0} -C %{buildroot}
install -D -m 0644 %{SOURCE1} %{buildroot}%{_prefix}/lib/firewalld/services/bobine.xml

%pre
# Mise à jour (deux versions installées simultanément) : arrêter Bobine AVANT le
# remplacement des fichiers, comme le prerm du .deb. Sentinelle posée par la mise à jour
# interne de Bobine : il se relance alors lui-même.
if [ "$1" -ge 2 ] && [ ! -f /tmp/bobine-self-update-in-progress ]; then
    if pgrep -x BobineTray >/dev/null 2>&1 || pgrep -x BobineBackend >/dev/null 2>&1; then
        touch /run/bobine-restart-after-upgrade 2>/dev/null || touch /tmp/bobine-restart-after-upgrade 2>/dev/null || true
    fi
    pkill -x BobineTray >/dev/null 2>&1 || true
    pkill -x BobineBackend >/dev/null 2>&1 || true
fi
exit 0

%post
/usr/lib/bobine/configure-storage-access auto
# Raccourci sur le Bureau de l'utilisateur qui a lancé dnf via sudo.
if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [ -n "$USER_HOME" ] && [ -d "$USER_HOME" ]; then
        for candidate in "$USER_HOME/Desktop" "$USER_HOME/Bureau"; do
            if [ -d "$candidate" ]; then
                rm -f "$candidate/bobine.desktop" 2>/dev/null || true
                cp /usr/share/applications/com.bobine.app.desktop "$candidate/com.bobine.app.desktop"
                chown "$SUDO_USER:" "$candidate/com.bobine.app.desktop" 2>/dev/null || true
                chmod 0755 "$candidate/com.bobine.app.desktop" 2>/dev/null || true
                if command -v gio >/dev/null 2>&1; then
                    su - "$SUDO_USER" -c "gio set '$candidate/com.bobine.app.desktop' metadata::trusted true" 2>/dev/null || true
                fi
                break
            fi
        done
    fi
fi
if [ -d /etc/skel/Desktop ]; then
    rm -f /etc/skel/Desktop/bobine.desktop 2>/dev/null || true
    cp /usr/share/applications/com.bobine.app.desktop /etc/skel/Desktop/com.bobine.app.desktop
    chmod 0755 /etc/skel/Desktop/com.bobine.app.desktop
fi
# Appliance headless (installée par install.sh) : relance des services système si actifs.
if systemctl is-active --quiet bobine-backend.service 2>/dev/null; then
    systemctl daemon-reload 2>/dev/null || true
    systemctl restart bobine-backend.service 2>/dev/null || true
    if systemctl is-active --quiet bobine-kiosk.service 2>/dev/null; then
        systemctl restart bobine-kiosk.service 2>/dev/null || true
    fi
fi
exit 0

%posttrans
# Relance de l'application de bureau si elle tournait avant la mise à jour (exécuté
# après la suppression de l'ancienne version : ordre RPM différent de celui de dpkg).
if [ -f /run/bobine-restart-after-upgrade ] || [ -f /tmp/bobine-restart-after-upgrade ]; then
    rm -f /run/bobine-restart-after-upgrade /tmp/bobine-restart-after-upgrade 2>/dev/null || true
    if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
        USER_ID=$(id -u "$SUDO_USER" 2>/dev/null || echo "")
        if [ -n "$USER_ID" ] && [ -d "/run/user/$USER_ID" ]; then
            su - "$SUDO_USER" -c "XDG_RUNTIME_DIR=/run/user/$USER_ID systemctl --user daemon-reload" 2>/dev/null || true
            su - "$SUDO_USER" -c "XDG_RUNTIME_DIR=/run/user/$USER_ID systemctl --user restart bobine.service" 2>/dev/null || true
        fi
        if ! pgrep -u "$SUDO_USER" -x BobineTray >/dev/null 2>&1; then
            su - "$SUDO_USER" -c "nohup /usr/bin/bobine >/dev/null 2>&1 &" 2>/dev/null || true
        fi
    fi
fi
exit 0

%preun
if [ "$1" = 0 ]; then /usr/lib/bobine/configure-storage-access remove; fi
# Désinstallation complète uniquement ($1 = 0) : arrêt des processus Bobine.
if [ "$1" -eq 0 ]; then
    pkill -x BobineTray >/dev/null 2>&1 || true
    pkill -x BobineBackend >/dev/null 2>&1 || true
fi
exit 0

%postun
if [ "$1" -eq 0 ]; then
    if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
        USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        if [ -n "$USER_HOME" ]; then
            rm -f "$USER_HOME/Desktop/bobine.desktop" "$USER_HOME/Bureau/bobine.desktop" 2>/dev/null || true
            rm -f "$USER_HOME/Desktop/com.bobine.app.desktop" "$USER_HOME/Bureau/com.bobine.app.desktop" 2>/dev/null || true
        fi
    fi
    rm -f /etc/skel/Desktop/bobine.desktop /etc/skel/Desktop/com.bobine.app.desktop 2>/dev/null || true
fi
exit 0

%files
%defattr(-,root,root,-)
%license /usr/share/doc/bobine/copyright
/usr/lib/bobine
/usr/share/bobine
/usr/bin/bobine
/usr/lib/systemd/user/bobine.service
%config(noreplace) /etc/xdg/autostart/com.bobine.app.desktop
/usr/share/applications/com.bobine.app.desktop
/usr/share/metainfo/com.bobine.app.metainfo.xml
/usr/share/icons/hicolor/*/apps/bobine.png
/usr/share/icons/hicolor/*/apps/com.bobine.app.png
/usr/share/pixmaps/bobine.png
/usr/share/pixmaps/com.bobine.app.png
/usr/lib/firewalld/services/bobine.xml

%changelog
* Fri Oct 23 2026 FantasmaGlad <193235053+FantasmaGlad@users.noreply.github.com> - %{bobine_version}-%{bobine_release}
- Paquet RPM construit depuis l'arbre PyInstaller du .deb (voir docs/hebergement-paquets.md).
