# Publier Bobine sur Google Play

Deux applications Android sont publiées : `com.bobine.app` (téléphone et tablette) et
`com.bobine.app.tv` (Android TV). Google Play exige des bundles `.aab` ; les APK de la
page de téléchargement restent distribués séparément.

## Construire les bundles d'une version Stable

1. GitHub > onglet **Actions** > **Google Play (AAB)** > **Run workflow**.
2. Renseigner le tag Stable (par exemple `V5.0.0`). Cocher « Joindre les .aab à la release
   GitHub » pour retrouver les fichiers sur la page de la release.
3. À la fin du run, télécharger l'artefact `bobine-play-aab-<version>` : il contient
   `Bobine-<version>.aab` et `Bobine-TV-<version>.aab`.

## Bundles de la version 5.0.0

Construits depuis le tag `V5.0.0` et joints à sa release GitHub. Un `.aab` n'est pas installable
sur un appareil : il sert uniquement à être téléversé sur la console Google Play.

- [Bobine-5.0.0.aab](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-5.0.0.aab) — `com.bobine.app` (téléphone et tablette)
- [Bobine-TV-5.0.0.aab](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.0/Bobine-TV-5.0.0.aab) — `com.bobine.app.tv` (Android TV)

Le workflow refuse un tag Bêta ou Canary, vérifie la signature de chaque bundle et affiche
le `versionCode`. Celui-ci est le nombre de commits du tag, comme pour les APK : il croît à
chaque version, ce qui permet à Google Play d'accepter les mises à jour successives.

## Envoyer sur Google Play

- **À la main** : console Google Play > l'application > Production (ou Test interne) >
  Créer une version > téléverser le `.aab`. Faire de même pour l'application TV.
- **Automatiquement** : créer un compte de service Google Cloud autorisé sur la console Play,
  enregistrer sa clé JSON dans le secret GitHub `PLAY_SERVICE_ACCOUNT_JSON`, puis choisir la
  piste dans le formulaire du workflow. Les bundles partent alors en **brouillon** : la
  publication finale reste une validation manuelle dans la console.

## Signature

Les bundles sont signés avec la clé de téléversement (secrets `ANDROID_KEYSTORE_BASE64`,
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`). Activer la
signature par Google Play (App Signing) à la première publication : Google conserve la clé
de distribution et ne demande que la clé de téléversement pour les versions suivantes.

## Mises à jour des utilisateurs

Une application installée depuis Google Play se met à jour par le Play Store ; celle
installée depuis un APK GitHub se met à jour depuis les Réglages de Bobine. Les deux
installations ne sont pas interchangeables : la signature diffère (clé de distribution
Google contre clé de téléversement). Pour passer de l'une à l'autre, désinstaller puis
réinstaller après une sauvegarde (Réglages > Sauvegarde).
