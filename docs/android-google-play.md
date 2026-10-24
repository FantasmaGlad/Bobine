<p align="center">
  <img alt="Bobine" src="../Assets/Images/LogoBanniere.png" width="70%">
</p>

<h1 align="center">Bobine pour Android — Distribution et publication Google Play</h1>

<p align="center">
  <a href="android-google-play.md">Français</a> · <a href="android-google-play.en.md">English</a>
</p>

Ce document décrit comment les applications Android de Bobine sont construites, signées, distribuées
et publiées sur Google Play. Il s'adresse aux mainteneurs du projet ; ce n'est pas un guide
d'utilisation (voir le [README](../README.fr.md) pour l'installation côté utilisateur).

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Prérequis](#2-prérequis)
3. [Construire les bundles d'une version Stable](#3-construire-les-bundles-dune-version-stable)
   - [Le build Google Play](#le-build-google-play)
4. [Numérotation des versions](#4-numérotation-des-versions)
5. [Signature](#5-signature)
6. [Publier sur Google Play](#6-publier-sur-google-play)
7. [Points à vérifier dans la console Play](#7-points-à-vérifier-dans-la-console-play)
8. [Mises à jour côté utilisateur](#8-mises-à-jour-côté-utilisateur)
9. [Dépannage](#9-dépannage)

---

## 1. Vue d'ensemble

Bobine publie **deux applications Android** à partir du même code source. Elles sont issues de
deux variantes de build (*flavors*) et se distinguent par leur identifiant d'application : elles
peuvent donc coexister sur un même appareil et disposent chacune de leur fiche sur Google Play.

| Logo | Application | Identifiant | Appareils ciblés | Android minimum | Architectures | Installation directe | Google Play |
|:---:|---|---|---|:---:|---|---|---|
| <img alt="Bobine" src="../frontend/public/icon-192.png" width="56"> <br> ![Android](https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white) | **Bobine** (téléphone et tablette) | `com.bobine.app` | Téléphones, tablettes (Snapdragon 8 Gen 2/3, Dimensity, Tensor), ordinateurs portables Google Book (Aluminium OS) | 14 (API 34) | `arm64-v8a` | [Bobine-5.0.5.apk](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.5/Bobine-5.0.5.apk) | [Bobine-5.0.5.aab](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.5/Bobine-5.0.5.aab) |
| <img alt="Bobine TV" src="../frontend/public/icon-192.png" width="56"> <br> ![Android TV](https://img.shields.io/badge/Android_TV-009688?style=flat-square&logo=android&logoColor=white) | **Bobine TV** (Android TV et Google TV) | `com.bobine.app.tv` | Boîtiers et téléviseurs Android TV / Google TV, télécommande directionnelle | 14 (API 34) | `armeabi-v7a`, `arm64-v8a` | [Bobine-TV-5.0.5.apk](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.5/Bobine-TV-5.0.5.apk) | [Bobine-TV-5.0.5.aab](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.5/Bobine-TV-5.0.5.aab) |

<p align="center">
  <img alt="Bobine Android" src="../Assets/Images/AndroidRelease.png" width="82%">
</p>

> **APK et AAB : quelle différence ?** L'**APK** s'installe directement sur un appareil (page de
> téléchargement, ADB). L'**AAB** (*Android App Bundle*) est le format de **dépôt** exigé par
> Google Play : il n'est pas installable tel quel et sert uniquement à être téléversé dans la
> console. Google Play en génère ensuite les APK adaptés à chaque appareil.

Chaque application embarque son propre serveur Bobine (CPython et FastAPI via Chaquopy) exécuté dans
un service de premier plan : aucune connexion à un serveur distant n'est nécessaire.

## 2. Prérequis

| Élément | Détail |
|---|---|
| Compte Google Play Console | Compte développeur avec les deux fiches d'application créées (`com.bobine.app` et `com.bobine.app.tv`). |
| Clé de téléversement | Keystore PKCS12 (alias `bobine`). Conservé hors du dépôt, sauvegardé hors de la machine de build. |
| Secrets GitHub Actions | `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`. |
| Secret facultatif | `PLAY_SERVICE_ACCOUNT_JSON` : clé d'un compte de service Google Cloud autorisé sur la console Play, pour l'envoi automatique. |
| Version Stable | Un tag `Vx.y.z` existant (les versions Bêta et Canary ne sont jamais publiées sur Google Play). |

> **Sauvegarde de la clé.** Sans la clé de téléversement, aucune mise à jour future ne pourra être
> signée pour la fiche existante. Conservez le keystore et son mot de passe dans un coffre chiffré,
> en deux endroits distincts. Ne les ajoutez jamais au dépôt.

## 3. Construire les bundles d'une version Stable

Le workflow [`play-aab.yml`](../.github/workflows/play-aab.yml) (**Google Play (AAB)**) se lance à la
main depuis GitHub.

1. Ouvrir l'onglet **Actions**, choisir **Google Play (AAB)**, puis **Run workflow**.
2. Renseigner les paramètres :

   | Paramètre | Valeur | Rôle |
   |---|---|---|
   | `tag` | `V5.0.5` (obligatoire) | Version Stable à construire. Le code est celui de ce tag exact. |
   | `source_ref` | vide, ou `main` | Branche ou tag à construire. Vide : le tag lui-même. Permet de construire le build Play depuis `main` sans déplacer le tag. |
   | `attach_to_release` | `true` / `false` | Joint les `.aab` et les APK Play à la release GitHub du tag (remplace les fichiers de même nom). |
   | `play_track` | `internal`, `alpha`, `beta`, `production` | Piste de destination, utilisée **uniquement** si `PLAY_SERVICE_ACCOUNT_JSON` est configuré. |

3. À la fin du run, récupérer les fichiers dans l'artefact `bobine-play-aab-<version>` (et sur la
   page de la release si `attach_to_release` est activé) :

   | Fichier | Application |
   |---|---|
   | `Bobine-<version>.aab` | `com.bobine.app` |
   | `Bobine-TV-<version>.aab` | `com.bobine.app.tv` |
   | `Bobine-<version>-play.apk` | `com.bobine.app` (APK équivalent au bundle) |
   | `Bobine-TV-<version>-play.apk` | `com.bobine.app.tv` (APK équivalent au bundle) |

Le workflow refuse un tag Bêta ou Canary, vérifie la signature de chaque bundle (`jarsigner`) et la
présence du manifeste, vérifie que les APK Play ne contiennent pas l'autorisation `REQUEST_INSTALL_PACKAGES`, vérifie les ABI natives (`arm64-v8a` pour Bobine, `armeabi-v7a` et `arm64-v8a` pour Bobine TV) et la présence du composant audio natif `libbobine_media.so` dans chacune (compilé par `scripts/ci/build-media-android.sh`), puis affiche le `versionName` et le `versionCode` dans le résumé du run. Le composant est désactivé par défaut dans l'application (Réglages → Composant audio natif) ; sa présence dans les paquets ne dit rien de son comportement sur un appareil réel, aucune mesure n'en ayant été faite.

### Fichiers Google Play de la version 5.0.5

| Logo | Application | Identifiant | Appareils | Format | Taille | Téléchargement |
|:---:|---|---|---|---|---:|---|
| <img alt="Bobine" src="../frontend/public/icon-192.png" width="48"> <br> ![Android](https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white) | **Bobine** | `com.bobine.app` | Téléphones, tablettes, Google Book | Bundle `.aab` (dépôt Google Play) | ~49 Mo | [Bobine-5.0.5.aab](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.5/Bobine-5.0.5.aab) |
| <img alt="Bobine" src="../frontend/public/icon-192.png" width="48"> <br> ![Android](https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white) | **Bobine** | `com.bobine.app` | Téléphones, tablettes, Google Book | APK Play (test et installation directe) | — | [Bobine-5.0.5-play.apk](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.5/Bobine-5.0.5-play.apk) |
| <img alt="Bobine" src="../frontend/public/icon-192.png" width="48"> <br> ![Android TV](https://img.shields.io/badge/Android_TV-009688?style=flat-square&logo=android&logoColor=white) | **Bobine TV** | `com.bobine.app.tv` | Android TV, Google TV | Bundle `.aab` (dépôt Google Play) | ~71 Mo | [Bobine-TV-5.0.5.aab](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.5/Bobine-TV-5.0.5.aab) |
| <img alt="Bobine" src="../frontend/public/icon-192.png" width="48"> <br> ![Android TV](https://img.shields.io/badge/Android_TV-009688?style=flat-square&logo=android&logoColor=white) | **Bobine TV** | `com.bobine.app.tv` | Android TV, Google TV | APK Play (test et installation directe) | — | [Bobine-TV-5.0.5-play.apk](https://github.com/FantasmaGlad/Bobine/releases/download/V5.0.5/Bobine-TV-5.0.5-play.apk) |

## Le build Google Play

Google Play interdit à une application distribuée par la boutique de se mettre à jour autrement que
par le Play Store. Les bundles `.aab` et les APK `-play.apk` sont donc construits avec une variante
dédiée (`play`, définie dans `android/app/build.gradle.kts`) :

| Élément | APK GitHub (`release`) | Build Google Play (`play`) |
|---|---|---|
| Autorisation `REQUEST_INSTALL_PACKAGES` | Présente | **Retirée** (`android/app/src/play/AndroidManifest.xml`) |
| Mise à jour intégrée (Réglages > Mises à jour) | Active, depuis les releases GitHub | **Suit le processus Google Play** : état de la mise à jour, « Mettre à jour via Google Play », « Redémarrer pour installer », « Ouvrir Google Play » ; aucun APK n'est téléchargé ni installé |
| Requête vers GitHub pour les mises à jour | Oui | Aucune |
| Signature | Clé de téléversement | Clé de téléversement (Google re-signe pour la distribution) |

L'APK `-play.apk` est le même build que le bundle : il permet de tester sur un appareil ce que les
utilisateurs de Google Play recevront. Pour une installation classique hors Play, utilisez l'APK de
la release (`Bobine-<version>.apk`), qui conserve la mise à jour intégrée.

## 4. Numérotation des versions

- **`versionName`** : le numéro du tag sans le `V` (`V5.0.2` donne `5.0.2`).
- **`versionCode`** : le nombre de commits du tag. Il croît à chaque version, ce qui permet à Google
  Play d'accepter les mises à jour successives, et il suit la même règle que les APK.

Google Play refuse un bundle dont le `versionCode` n'est pas strictement supérieur à celui déjà
publié sur la piste. Après un déplacement de tag vers un commit plus récent, le `versionCode`
augmente : reconstruire alors les bundles avant tout nouveau téléversement.

## 5. Signature

Les bundles sont signés avec la **clé de téléversement** (les quatre secrets `ANDROID_KEY*`). Activez
**Play App Signing** à la première publication : Google conserve la clé de distribution, et seule la
clé de téléversement est ensuite demandée pour chaque version. En cas de perte de cette dernière, la
console permet d'en enregistrer une nouvelle après vérification d'identité.

## 6. Publier sur Google Play

### Envoi manuel

1. Console Google Play, choisir l'application.
2. **Test interne** (recommandé pour un premier envoi) ou **Production**, puis **Créer une version**.
3. Téléverser le `.aab` correspondant, renseigner les notes de version, enregistrer et lancer
   l'examen.
4. Répéter l'opération pour la seconde application.

### Envoi automatique

1. Créer un compte de service Google Cloud et l'autoriser dans la console Play (accès aux versions).
2. Enregistrer sa clé JSON dans le secret GitHub `PLAY_SERVICE_ACCOUNT_JSON`.
3. Lancer le workflow en choisissant la piste (`play_track`).

Les bundles sont alors envoyés en **brouillon** : la mise en ligne finale reste une validation
manuelle dans la console.

## 7. Points à vérifier dans la console Play

Google Play examine les autorisations sensibles et le mode de mise à jour des applications. Les
points suivants sont à traiter avant la mise en production ; ils ne préjugent pas de la décision de
l'examen.

| Sujet | Autorisation ou fonction | À préparer |
|---|---|---|
| Service de premier plan | `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_SPECIAL_USE` | Déclaration du type d'usage et justification : le serveur Bobine doit rester actif pendant les cours. |
| Démarrage de l'appareil | `RECEIVE_BOOT_COMPLETED` | Fonction facultative, activée par l'utilisateur dans Réglages > Démarrage de l'appareil. |
| Affichage par-dessus d'autres applications | `SYSTEM_ALERT_WINDOW` | Justification de l'ouverture de l'écran au démarrage. |
| Optimisation de batterie | `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | Justification : lecture continue en salle. |
| Installation d'applications | `REQUEST_INSTALL_PACKAGES` | Retirée du build Google Play (voir [Le build Google Play](#le-build-google-play)) : aucune déclaration à remplir pour cette autorisation. |
| Données et confidentialité | Aucune télémétrie, fonctionnement hors ligne | Formulaire « Sécurité des données » : aucune collecte, aucun partage. |

## 8. Mises à jour côté utilisateur

Une application installée depuis Google Play se met à jour par le Play Store ; celle installée depuis
un APK GitHub se met à jour depuis les Réglages de Bobine. Les deux installations **ne sont pas
interchangeables** : la signature diffère (clé de distribution Google contre clé de téléversement).
Pour passer de l'une à l'autre, sauvegarder les données (Réglages > Sauvegarde), désinstaller, puis
réinstaller.

## 9. Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| La console refuse le bundle (« code de version déjà utilisé ») | `versionCode` non supérieur à celui déjà publié | Reconstruire depuis un tag plus récent. |
| Le workflow s'arrête sur le format du tag | Tag Bêta, Canary ou mal formé | Utiliser un tag Stable `Vx.y.z`. |
| Build ignoré avec un avertissement | Secrets `ANDROID_KEYSTORE_*` absents | Ajouter les secrets (section 2). |
| Aucun envoi sur Play malgré le workflow réussi | `PLAY_SERVICE_ACCOUNT_JSON` non configuré | Envoi manuel (section 6) ou ajout du secret. |
| Le bundle ne s'installe pas sur l'appareil | Un `.aab` n'est pas installable | Utiliser l'APK, ou téléverser le bundle sur Play. |

## Documents associés

- [Notes de version 5.0.2](releases/V5.0.2.md)
- [Architecture technique](ARCHITECTURE.md) (section Android)
- [README](../README.fr.md)
