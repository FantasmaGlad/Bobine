#!/usr/bin/env bash
# La clé privée est importée par le job appelant dans un GNUPGHOME éphémère.
# Les demandes de fusion ne lancent jamais cette étape.
set -euo pipefail
export LC_ALL=C
packages="${1:?dossier des paquets}"
fingerprint="${BOBINE_SIGNING_FINGERPRINT:-B77D96D72F84F36ACAA3F8729CBF497D829EE15A}"
[[ "$fingerprint" =~ ^[A-F0-9]{40}$ ]] || exit 2
actual=$(gpg --batch --with-colons --list-secret-keys "$fingerprint" | awk -F: '$1=="fpr" {print $10; exit}')
[ "$actual" = "$fingerprint" ] || { echo 'Clé de signature inattendue.' >&2; exit 1; }
key=$(mktemp); trap 'rm -f "$key"' EXIT
gpg --batch --armor --export "$fingerprint" > "$key"
rpm --import "$key"
count=0
while IFS= read -r -d '' package; do
    case "$package" in
        *.rpm)
            # Ces macros fonctionnent avec RPM 4 et RPM 6 (rpmsign(8)).
            rpmsign --define "_gpg_name $fingerprint" --define "_openpgp_sign_id $fingerprint" \
                --define "__gpg $(command -v gpg)" --addsign "$package"
            verification=$(rpmkeys --checksig "$package")
            echo "$verification"
            [[ "$verification" == *"digests signatures OK"* ]] || exit 1
            ;;
        *.pkg.tar.zst)
            gpg --batch --yes --local-user "$fingerprint" --detach-sign --output "$package.sig" "$package"
            gpg --batch --verify "$package.sig" "$package"
            ;;
        *) continue ;;
    esac
    count=$((count+1))
done < <(find "$packages" -type f \( -name '*.rpm' -o -name '*.pkg.tar.zst' \) -print0)
[ "$count" = 4 ] || { echo "Quatre paquets attendus, $count trouvés." >&2; exit 1; }
