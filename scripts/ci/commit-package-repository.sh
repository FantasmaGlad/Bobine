#!/usr/bin/env bash
# Commit des fichiers générés d'une copie du dépôt Pages (gh-pages) et poussée avec reprise : un autre écrivain peut avoir poussé
# entre le checkout et la poussée (pages vitrines, autre publication). Le rejet déclenche un rebase sur la tête distante puis un
# nouvel essai ; un conflit de rebase est abandonné proprement et fait échouer l'étape plutôt que de perdre un des deux états.
# Les pages vitrines ne sont jamais ajoutées : seuls les chemins générés ci-dessous le sont.
# Usage : commit-package-repository.sh <copie du dépôt Pages> <message de commit>
# Variables : PUSH_ATTEMPTS (3), PUSH_RETRY_DELAY (5 s, multiplié par le numéro d'essai), PUSH_REMOTE (origin),
#             PUSH_BRANCH (gh-pages), DRY_RUN=true (commit local, aucune poussée).
set -euo pipefail
export LC_ALL=C
repo="${1:?copie du dépôt Pages}"; message="${2:?message de commit}"
remote="${PUSH_REMOTE:-origin}"; branch="${PUSH_BRANCH:-gh-pages}"
attempts="${PUSH_ATTEMPTS:-3}"; delay="${PUSH_RETRY_DELAY:-5}"
cd "$repo"
git config user.name fanta
git config user.email 193235053+FantasmaGlad@users.noreply.github.com

# Les alias .repo de la racine sont écrits par prepare-package-repository.sh (famille rpm) : ils font partie des chemins publiés.
generated=(debian/ fedora/ arch/ bobine.gpg bobine.repo bobine-stable.repo bobine-beta.repo bobine-canary.repo latest.json mirror-packages.json)
staged=()
for path in "${generated[@]}"; do
    if [ -e "$path" ] || git ls-files --error-unmatch -- "$path" > /dev/null 2>&1; then staged+=("$path"); fi
done
[ "${#staged[@]}" -gt 0 ] || { echo "Aucun chemin publié dans $repo." >&2; exit 1; }
git add -A -- "${staged[@]}"
if git diff --cached --quiet; then
    echo "Aucun changement à publier."
    exit 0
fi
git commit -q -m "$message"
if [ "${DRY_RUN:-false}" = true ]; then
    echo "Essai sans publication : commit local seulement."
    git show --stat --format='%h %s' HEAD
    exit 0
fi

for attempt in $(seq 1 "$attempts"); do
    if git push "$remote" "HEAD:refs/heads/$branch"; then
        exit 0
    fi
    [ "$attempt" -lt "$attempts" ] || break
    echo "Poussée refusée (essai $attempt sur $attempts) : rebase sur $remote/$branch." >&2
    git fetch "$remote" "$branch"
    if ! git rebase "$remote/$branch"; then
        git rebase --abort || true
        echo "Conflit de rebase : rien n'est poussé, relancer la publication." >&2
        exit 1
    fi
    sleep $((delay * attempt))
done
echo "Poussée impossible après $attempts essais." >&2
exit 1
