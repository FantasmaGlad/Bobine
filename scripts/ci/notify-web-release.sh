#!/usr/bin/env bash
# Déclenche le rafraîchissement du miroir après publication des paquets signés.
set -euo pipefail
case "${RELEASE_CHANNEL:-}" in stable|beta|canary) ;; *) echo 'Canal de publication invalide' >&2; exit 1 ;; esac
[[ "${RELEASE_SHA:-}" =~ ^[a-f0-9]{40}$ ]] || { echo 'Révision de publication invalide' >&2; exit 1; }
if [ -z "${BOBINE_WEB_DISPATCH_TOKEN:-}" ]; then
  echo '::warning::Notification BobineWeb inactive : configurer BOBINE_WEB_DISPATCH_TOKEN, limité au dépôt BobineWeb (Contents: write). Le miroir conserve son rafraîchissement quotidien.'
  exit 0
fi
payload=$(jq -n --arg channel "$RELEASE_CHANNEL" --arg sha "$RELEASE_SHA" \
  '{event_type:"bobine-release",client_payload:{repository:"FantasmaGlad/Bobine",channel:$channel,sha:$sha}}')
curl --fail --silent --show-error --retry 3 --max-time 30 \
  --request POST --header 'Accept: application/vnd.github+json' \
  --header "Authorization: Bearer $BOBINE_WEB_DISPATCH_TOKEN" \
  --header 'X-GitHub-Api-Version: 2026-03-10' \
  --data "$payload" https://api.github.com/repos/FantasmaGlad/BobineWeb/dispatches
echo "Notification BobineWeb transmise pour $RELEASE_CHANNEL ($RELEASE_SHA)."
