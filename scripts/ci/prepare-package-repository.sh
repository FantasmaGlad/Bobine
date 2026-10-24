#!/usr/bin/env bash
# Régénère uniquement le canal demandé ; les pages, jeux et autres canaux sont conservés.
# Dépendances : createrepo_c, rpmkeys, GnuPG, Docker (repo-add officiel Arch).
set -euo pipefail
export LC_ALL=C
family="${1:?rpm ou arch}"; channel="${2:?stable, beta ou canary}"
packages=$(realpath "${3:?paquets signés}"); destination=$(realpath "${4:?copie du dépôt Pages}")
case "$family" in rpm|arch) ;; *) exit 2 ;; esac
case "$channel" in stable|beta|canary) ;; *) exit 2 ;; esac
[ "$destination" != / ] && [ "$destination" != "$packages" ] || exit 2
fingerprint="${BOBINE_SIGNING_FINGERPRINT:-B77D96D72F84F36ACAA3F8729CBF497D829EE15A}"
[[ "$fingerprint" =~ ^[A-F0-9]{40}$ ]] || exit 2
gpg --batch --armor --export "$fingerprint" > "$destination/bobine.gpg"
test -s "$destination/bobine.gpg"
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
        "${CONTAINER_ENGINE:-docker}" run --rm --network=none -v "$target:/repo" archlinux:latest \
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
fi
