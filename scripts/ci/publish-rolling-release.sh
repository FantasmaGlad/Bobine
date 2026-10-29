#!/usr/bin/env bash
# Publie ou met à jour la release d'un canal glissant (canary, beta) EN PLACE : la release n'est jamais supprimée, donc plus de
# 404 de 30 à 60 secondes à chaque publication, et un échec ne laisse plus le canal sans release. Les assets du même nom sont
# remplacés (--clobber), les assets qui ne font plus partie du lot sont retirés, puis titre et notes sont mis à jour. SHA256SUMS et
# sa signature sont envoyés en dernier. Seul le remplacement d'un asset donné est indisponible, le temps de son envoi.
# Usage : publish-rolling-release.sh <tag> <dossier des assets> <titre> <fichier de notes> [commit cible]
# Dépendances : gh, GH_TOKEN (ou gh déjà authentifié). Le tag doit déjà pointer sur le commit publié.
set -euo pipefail
export LC_ALL=C
tag="${1:?tag mobile (canary ou beta)}"; dir="${2:?dossier des assets}"; title="${3:?titre}"; notes="${4:?fichier de notes}"
target="${5:-}"
[ -d "$dir" ] && [ -s "$notes" ] || { echo "Assets ou notes introuvables." >&2; exit 2; }
shopt -s nullglob
assets=("$dir"/*)
[ "${#assets[@]}" -gt 0 ] || { echo "Aucun asset à publier." >&2; exit 2; }
checksums=()
others=()
for asset in "${assets[@]}"; do
    case "$(basename "$asset")" in SHA256SUMS|SHA256SUMS.asc) checksums+=("$asset") ;; *) others+=("$asset") ;; esac
done

if ! lookup=$(gh release view "$tag" --json assets --jq '.assets[].name' 2>&1); then
    # Seule l'absence de la release autorise la création ; toute autre erreur (réseau, droits) arrête la publication.
    case "$lookup" in
        *"release not found"*) ;;
        *) echo "$lookup" >&2; exit 1 ;;
    esac
    gh release create "$tag" "${others[@]}" "${checksums[@]}" \
        --title "$title" --notes-file "$notes" --prerelease ${target:+--target "$target"}
    exit 0
fi

[ "${#others[@]}" -eq 0 ] || gh release upload "$tag" "${others[@]}" --clobber
[ "${#checksums[@]}" -eq 0 ] || gh release upload "$tag" "${checksums[@]}" --clobber
while IFS= read -r name; do
    [ -n "$name" ] && [ ! -e "$dir/$name" ] && gh release delete-asset "$tag" "$name" --yes
done <<< "$lookup"
gh release edit "$tag" --title "$title" --notes-file "$notes" --prerelease
echo "Release $tag mise à jour en place : ${#assets[@]} assets."
