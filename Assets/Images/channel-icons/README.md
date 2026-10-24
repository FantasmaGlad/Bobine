# Icônes des canaux de version (Stable, Bêta, Canary)

Ce dossier est la **source unique** des icônes par canal. Tout le reste est généré : ne jamais modifier à la main un fichier dérivé, relancer le générateur.

| Fichier | Rôle |
| --- | --- |
| `bobine-channel-stable.png` | Icône Stable : ruban argent / blanc titane |
| `bobine-channel-beta.png` | Icône Bêta : ruban bleu cobalt |
| `bobine-channel-canary.png` | Icône Canary : ruban or solaire |
| `banner-wordmark.png` | Texte « obine » de la bannière Android TV (le « B » est l'icône du canal) |

Format des icônes : 512 x 512, PNG RGBA, fond transparent, Baamix et perforations inchangés d'un canal à l'autre (seule la teinte du ruban varie).

## Régénérer

```bash
python3 scripts/generate_channel_icons.py            # écrit tous les dérivés
python3 scripts/generate_channel_icons.py --check    # échoue si un dérivé est absent ou périmé
python3 scripts/generate_channel_icons.py --list     # liste les fichiers produits
```

Dépendance : Pillow. `backend/tests/test_channel_icons_wiring.py` (lancé par la suite pytest et la CI) échoue si un dérivé est périmé ou si le câblage diverge.

## Deux notions de canal, deux mécanismes

| Surface | Canal utilisé | Quand l'icône change |
| --- | --- | --- |
| Lanceur / tiroir d'applications Android, bannière Android TV | canal du **build** | à l'installation du build du canal |
| Icône des exécutables et de l'installeur Windows, du bundle macOS, du lanceur Linux (`.deb`, `.rpm`, Arch) | canal du **build** | à l'installation du paquet du canal |
| Barre système (tray) Windows, macOS, Linux | canal **choisi** (Réglages) | à chaud, dans les 15 secondes |
| Logo de l'interface web, favicon de l'onglet | canal **choisi** | à chaud |
| Écran de démarrage Android | canal **choisi** | au prochain lancement |

Pourquoi : changer de canal dans les Réglages installe le build de l'autre canal (APK, installeur, paquet distincts), qui apporte sa propre icône. Une icône de lanceur modifiable à chaud (alias d'activité Android, surcharge dans le dossier utilisateur Linux) ferait disparaître des raccourcis épinglés selon les lanceurs ; elle n'apporterait rien de plus.

**Une seule règle, un seul registre** : `backend/app/release_channel.py` (bibliothèque standard uniquement) déclare les canaux et implémente la règle. Il est importé par le backend (réglages, mises à jour, barre système) et chargé par son chemin par les outils de construction (specs PyInstaller, scripts de paquetage via `packaging/common/channel.py`, générateur d'icônes). Gradle/Kotlin et le frontend en reçoivent des fichiers **générés** (`android/release-channels.json`, `frontend/src/lib/releaseChannels.generated.ts`) par `python3 scripts/sync_release_channels.py` ; `--check` échoue s'ils sont périmés. `backend/tests/test_release_channels_wiring.py` interdit à un consommateur de réécrire une liste ou une règle de canaux.

Trois notions :

- **canal du build** : suffixe de `VERSION` que la CI écrit avant la construction (`5.0.5-beta`, `5.0.5-canary`, `5.0.5+canary.42` pour un paquet Debian), sinon Stable. Il fixe les icônes de lanceur, d'installeur et d'exécutable.
- **canal d'installation** : celui que l'utilisateur a rejoint en installant. C'est le canal du build ; pour une installation depuis les sources (`install.sh`, appliance), le canal enregistré dans `/etc/bobine/update-channel` (ignoré par un build figé, qui a déjà tranché).
- **canal effectif** : celui des mises à jour proposées et de toutes les icônes affichées. Sans choix de l'utilisateur, c'est le canal d'installation (aucune ligne n'est écrite en base : « pas de ligne » signifie « suivre l'installation ») ; un choix explicite dans les Réglages l'emporte toujours. `GET /api/settings` expose `update_channel`, `update_channel_source` (`user` ou `install`) et `install_channel`.

**Google Play** : un build distribué par la boutique est verrouillé sur la Stable (`resolve_update_channel`, `update_channel_source = locked`) : il ne se met à jour que par le Play Store, qui ne publie que des Stables (`play-aab.yml` refuse les versions `-beta` et `-canary`), le sélecteur de canal est masqué, `PUT /api/settings` refuse un autre canal (409) et toutes ses icônes restent celles de la Stable, même si un réglage Canary est restauré depuis une sauvegarde.

Une installation Canary propose donc les mises à jour Canary et affiche toutes les icônes Canary d'emblée, sur Android, Windows, macOS et Linux, avec la possibilité de changer de canal.

## Fichiers générés

| Plateforme | Fichiers | Consommateur |
| --- | --- | --- |
| Linux | `packaging/linux/icons/<canal>/hicolor/<taille>/apps/com.bobine.app.png`, `.../pixmaps/` | `channel.sh` (`install_channel_icons`), appelé par `build_deb.sh` et `stage_root.sh` ; installés sous `com.bobine.app` et `bobine` |
| Windows | `packaging/windows/bobine-<canal>.ico` | `bobine.spec` (exécutables, copie `bobine.ico`), `bobine.iss` (installeur) |
| macOS | `packaging/macos/bobine-<canal>.icns` | `bobine.spec` (copie sous le nom fixe `bobine.icns`) |
| Android | `android/app/src/channel-<canal>/res/mipmap-*/ic_launcher_foreground.png`, `android/app/src/tv-channel-<canal>/res/drawable/banner_bobine_tv.png`, `android/app/src/main/res/drawable-nodpi/bobine_splash_logo_<canal>.png` | `app/build.gradle.kts` (ressources du canal du build), `SplashChannel.kt` |
| Barre système | `Assets/Images/logo_bobine_icon_<canal>.png` (+ `logo_bobine_icon.png` = Stable) | `channel.py` embarque les quatre dans chaque build ; `channel_icon.py` choisit à l'exécution |
| Interface web | `frontend/public/logo-<canal>.png`, `frontend/public/favicon-<canal>.png` | `frontend/src/lib/releaseChannel.ts` |
| Assistant d'installation | `assistant/ui/assets/channel-<canal>.png` | `assistant/ui/index.html` |
| README et notes de version | `Assets/Images/Versions/<Canal>.png`, `<Canal>-cropped-1024.png` | README, `docs/releases/` |

Le dépôt du site (BobineWeb) garde ses propres copies dans `public/images/channels/` : les remplacer à la main depuis `bobine-channel-<canal>.png` (256 px, PNG et WebP).

## Ajouter un canal

1. Ajouter une entrée à `CHANNELS` dans `backend/app/release_channel.py` (id, suffixe de version, tag de release).
2. Déposer `bobine-channel-<canal>.png` (512 x 512) ici.
3. Ajouter la ressource d'écran de démarrage Android et sa branche `when` dans `SplashChannel.kt` (le registre ne peut pas énumérer des ressources compilées).
4. `python3 scripts/sync_release_channels.py && python3 scripts/generate_channel_icons.py`.
5. `pytest backend/tests/test_release_channels_wiring.py backend/tests/test_channel_icons_wiring.py` : chaque oubli est signalé par un test nommé.

## Ajouter une cible

Ajouter une fonction de sortie dans `outputs_for_channel` du générateur, déclarer le consommateur dans ce tableau, puis un test dans `test_channel_icons_wiring.py`.

## Non couvert

- Icônes PWA du manifeste (`icon-192.png`, `icon-512.png`) et `apple-touch-icon` : statiques, une application installée ne peut pas changer d'icône à chaud.
- Icône de l'assistant Tauri (`assistant/src-tauri/icons`) : identité de l'assistant, indépendante du canal.
