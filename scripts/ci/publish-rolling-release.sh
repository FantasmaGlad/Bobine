#!/usr/bin/env bash
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
    case "$(basename "$asset")" in
        SHA256SUMS|SHA256SUMS.asc) checksums+=("$asset") ;;
        *) others+=("$asset") ;;
    esac
done

if ! lookup=$(gh release view "$tag" --json assets --jq '.assets[].name' 2>&1); then
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
gh release edit "$tag" --title "$title" --notes-file "$notes" --prerelease --draft=false
echo "Release $tag mise à jour en place : ${#assets[@]} assets."
