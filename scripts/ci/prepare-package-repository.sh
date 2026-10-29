#!/usr/bin/env bash
# Régénère uniquement le canal demandé ; les pages, jeux et autres canaux sont conservés.
# Dépendances : reprepro, createrepo_c, rpmkeys, GnuPG, Docker (repo-add officiel Arch).
set -euo pipefail
export LC_ALL=C
family="${1:?deb, rpm ou arch}"; channel="${2:?canal (stable, beta, canary...)}"
packages=$(realpath "${3:?paquets signés}"); destination=$(realpath "${4:?copie du dépôt Pages}")
case "$family" in deb|rpm|arch) ;; *) exit 2 ;; esac
. "$(dirname "$0")/container-images.sh"
# Canaux valides : le registre unique (backend/app/release_channel.py), pas une liste recopiée ici.
python3 "$(dirname "$0")/../../packaging/common/channel.py" is-channel "$channel" || exit 2
[ "$destination" != / ] && [ "$destination" != "$packages" ] || exit 2
fingerprint="${BOBINE_SIGNING_FINGERPRINT:-B77D96D72F84F36ACAA3F8729CBF497D829EE15A}"
[[ "$fingerprint" =~ ^[A-F0-9]{40}$ ]] || exit 2
gpg --batch --armor --export "$fingerprint" > "$destination/bobine.gpg"
test -s "$destination/bobine.gpg"

if [ "$family" = deb ]; then
    debian_dir="$destination/debian"
    [ ! -L "$debian_dir" ] || exit 2
    mkdir -p "$debian_dir/conf"
    if [ ! -f "$debian_dir/conf/distributions" ]; then
        cat > "$debian_dir/conf/distributions" <<EOF
Origin: Bobine
Label: Bobine Official Repository
Codename: stable
Architectures: amd64 arm64
Components: main
Description: Depot APT officiel pour Bobine (canal Stable)
SignWith: ${fingerprint: -16}
ValidFor: 365d

Origin: Bobine
Label: Bobine Official Repository (Beta)
Codename: beta
Architectures: amd64 arm64
Components: main
Description: Depot APT officiel pour Bobine (canal Beta)
SignWith: ${fingerprint: -16}
ValidFor: 365d

Origin: Bobine
Label: Bobine Official Repository (Canary)
Codename: canary
Architectures: amd64 arm64
Components: main
Description: Depot APT officiel pour Bobine (canal Canary)
SignWith: ${fingerprint: -16}
ValidFor: 30d
EOF
    elif ! grep -q "arm64" "$debian_dir/conf/distributions"; then
        sed -i 's/^Architectures: amd64$/Architectures: amd64 arm64/' "$debian_dir/conf/distributions"
    fi
    # Les dépôts existants reçoivent la même durée que les nouvelles installations (apt-validity.py : un an, 30 jours pour la Canary).
    python3 "$(dirname "$0")/apt-validity.py" apply "$debian_dir/conf/distributions"
    mapfile -d '' deb_amd64_matches < <(find "$packages" -type f -name "*_amd64.deb" -print0)
    mapfile -d '' deb_arm64_matches < <(find "$packages" -type f -name "*_arm64.deb" -print0)
    [ "${#deb_amd64_matches[@]}" = 1 ] && [ "${#deb_arm64_matches[@]}" = 1 ] || { echo "Deux paquets deb (amd64 et arm64) attendus." >&2; exit 1; }
    deb_amd64="${deb_amd64_matches[0]}"
    deb_arm64="${deb_arm64_matches[0]}"
    if [ "$channel" = beta ] || [ "$channel" = canary ]; then
        reprepro -b "$debian_dir" remove "$channel" bobine || true
        reprepro -b "$debian_dir" includedeb "$channel" "$deb_amd64"
        reprepro -b "$debian_dir" includedeb "$channel" "$deb_arm64"
    else
        deb_version="$(dpkg-deb -f "$deb_amd64" Version)"
        if reprepro -b "$debian_dir" list stable bobine | grep -q " ${deb_version}\$"; then
            reprepro -b "$debian_dir" remove stable bobine
        fi
        reprepro -b "$debian_dir" includedeb stable "$deb_amd64"
        reprepro -b "$debian_dir" includedeb stable "$deb_arm64"
    fi
    cat "$debian_dir"/dists/*/main/binary-*/Packages | sed -n 's/^Filename: //p' | sort -u > "$debian_dir/.referenced.txt"
    if [ -s "$debian_dir/.referenced.txt" ]; then
        (
            cd "$debian_dir"
            find pool -type f | sort > .pool-files.txt
            comm -23 .pool-files.txt .referenced.txt | xargs -r -d '\n' rm -f --
            find pool -type d -empty -delete
        )
    fi
    rm -f "$debian_dir/.referenced.txt" "$debian_dir/.pool-files.txt"
    gpg --batch --verify "$debian_dir/dists/$channel/InRelease"
    exit 0
fi

for arch in x86_64 aarch64; do
    if [ "$family" = rpm ]; then
        sub_dir="fedora"
        suffix=".$arch.rpm"
    else
        sub_dir="arch"
        suffix="-$arch.pkg.tar.zst"
    fi
    target="$destination/$sub_dir/$channel/$arch"
    # Aucun chemin de nettoyage ne vient du contenu d'un paquet.
    [ ! -L "$destination/$sub_dir" ] && [ ! -L "$destination/$sub_dir/$channel" ] && [ ! -L "$target" ] || exit 2
    mapfile -d '' matches < <(find "$packages" -type f -name "*$suffix" -print0)
    [ "${#matches[@]}" = 1 ] || { echo "Un paquet $family/$arch attendu." >&2; exit 1; }
    package="${matches[0]}"
    if [ "$family" = rpm ]; then
        verification=$(rpmkeys --checksig "$package")
        echo "$verification"
        [[ "$verification" == *"digests signatures OK"* ]] || exit 1
    else
        gpg --batch --verify "$package.sig" "$package"
    fi
    rm -rf "$target"
    mkdir -p "$target"
    cp "$package" "$target/"
    if [ "$family" = rpm ]; then
        createrepo_c "$target"
        gpg --batch --yes --local-user "$fingerprint" --armor --detach-sign "$target/repodata/repomd.xml"
        gpg --batch --verify "$target/repodata/repomd.xml.asc" "$target/repodata/repomd.xml"
    else
        cp "$package.sig" "$target/"
        "${CONTAINER_ENGINE:-docker}" run --rm --network=none -v "$target:/repo" "$ARCH_IMAGE" \
            bash -ec 'repo-add /repo/bobine.db.tar.gz /repo/*.pkg.tar.zst'
        for name in bobine.db bobine.files; do
            gpg --batch --yes --local-user "$fingerprint" --detach-sign "$target/$name.tar.gz"
            gpg --batch --verify "$target/$name.tar.gz.sig" "$target/$name.tar.gz"
            # Pages doit servir les octets de l'archive, pas le texte d'un lien symbolique Git.
            cp --remove-destination "$target/$name.tar.gz" "$target/$name"
            cp "$target/$name.tar.gz.sig" "$target/$name.sig"
        done
    fi
done
if [ "$family" = rpm ]; then
    mkdir -p "$destination/fedora"
    for suite in stable beta canary; do
        cat > "$destination/fedora/bobine-$suite.repo" <<EOF
[bobine-$suite]
name=Bobine ($suite)
baseurl=https://packages.bobine.fit/fedora/$suite/\$basearch/
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=https://packages.bobine.fit/bobine.gpg
EOF
        cp "$destination/fedora/bobine-$suite.repo" "$destination/bobine-$suite.repo"
    done
    cp "$destination/fedora/bobine-stable.repo" "$destination/fedora/bobine.repo"
    cp "$destination/fedora/bobine-stable.repo" "$destination/bobine.repo"
fi
