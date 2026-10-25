#!/usr/bin/env bash
# Signe la liste des empreintes SHA-256 des fichiers d'une release : produit SHA256SUMS et sa signature détachée
# SHA256SUMS.asc, avec la clé qui signe déjà les dépôts de paquets. Le site s'appuie sur ce couple pour afficher la commande
# de vérification (gpg --verify, puis sha256sum -c) des fichiers téléchargés en direct.
# La clé privée est importée par le job appelant dans un GNUPGHOME éphémère ; les demandes de fusion ne lancent jamais cette étape.
set -euo pipefail
export LC_ALL=C
dir="${1:?dossier des assets de la release}"
fingerprint="${BOBINE_SIGNING_FINGERPRINT:-B77D96D72F84F36ACAA3F8729CBF497D829EE15A}"
[[ "$fingerprint" =~ ^[A-F0-9]{40}$ ]] || exit 2
actual=$(gpg --batch --with-colons --list-secret-keys "$fingerprint" | awk -F: '$1=="fpr" {print $10; exit}')
[ "$actual" = "$fingerprint" ] || { echo 'Clé de signature inattendue.' >&2; exit 1; }

cd "$dir"
rm -f SHA256SUMS SHA256SUMS.asc
# Tous les fichiers du dossier, hors la liste et sa signature, dans l'ordre alphabétique.
find . -maxdepth 1 -type f ! -name 'SHA256SUMS*' -printf '%f\n' | sort | xargs -d '\n' sha256sum > SHA256SUMS
[ -s SHA256SUMS ] || { echo 'Aucun fichier à signer.' >&2; exit 1; }
gpg --batch --yes --armor --local-user "$fingerprint" --detach-sign --output SHA256SUMS.asc SHA256SUMS
gpg --batch --verify SHA256SUMS.asc SHA256SUMS
sha256sum --check --strict SHA256SUMS > /dev/null
echo "SHA256SUMS : $(wc -l < SHA256SUMS) fichiers, signature vérifiée."
