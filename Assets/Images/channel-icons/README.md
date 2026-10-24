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

**Canal du build** : déduit du suffixe de `VERSION`, que la CI écrit avant la construction (`5.0.5-beta`, `5.0.5-canary`), sinon Stable. La même règle existe à quatre endroits, vérifiés par le test de câblage : `backend/app/utils/version.py` (`build_channel_of_version`), `packaging/common/channel.py` (specs PyInstaller ; le `.iss` de l'installeur Windows reprend l'icône choisie par le spec), `packaging/common/channel.sh` (paquets Linux) et `android/app/build.gradle.kts` (`bobineChannel`, forçable avec `-PbobineChannel=<canal>`).

**Canal choisi** : réglage `update_channel` du backend (`GET /api/settings`). La barre système le relit toutes les 15 secondes (`backend/app/desktop/channel_icon.py`) ; l'interface le reçoit par WebSocket (`frontend/src/lib/releaseChannel.ts`) et le transmet à Android (`UpdateChannelPref`).

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

1. Déposer `bobine-channel-<canal>.png` (512 x 512) ici.
2. Ajouter le nom dans `CHANNELS` de `scripts/generate_channel_icons.py` et dans `VERSIONS_NAMES`, puis régénérer.
3. L'ajouter à `RELEASE_CHANNELS` (`backend/app/utils/version.py`), `RELEASE_CHANNELS` (`frontend/src/lib/releaseChannel.ts`), `CHANNELS` (`packaging/common/channel.py`), `releaseChannels` (`android/app/build.gradle.kts`), `VALID` (`NativeBridge.kt`) et la branche `when` de `SplashChannel.kt` ; adapter la regex de `channel.sh`, `channel.py` et `rolling_channel_of_version`.
4. Lancer `pytest backend/tests/test_channel_icons_wiring.py` : chaque oubli est signalé par un test nommé.

## Ajouter une cible

Ajouter une fonction de sortie dans `outputs_for_channel` du générateur, déclarer le consommateur dans ce tableau, puis un test dans `test_channel_icons_wiring.py`.

## Non couvert

- Icônes PWA du manifeste (`icon-192.png`, `icon-512.png`) et `apple-touch-icon` : statiques, une application installée ne peut pas changer d'icône à chaud.
- Icône de l'assistant Tauri (`assistant/src-tauri/icons`) : identité de l'assistant, indépendante du canal.
