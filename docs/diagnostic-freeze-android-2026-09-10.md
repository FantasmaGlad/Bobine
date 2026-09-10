# Diagnostic en cours — freeze vidéo Android (kiosk réseau)

Document de suivi de session (2026-09-10), pour reprise ultérieure. Décrit les règles suivies pendant l'investigation, les appareils/IP en jeu, et l'état exact du problème au moment de la pause.

---

## 1. Règles de la session

- **Aucune mention IA dans les commits** : pas de `Co-Authored-By`, pas de référence à Claude/IA dans les messages de commit ou la documentation. Pas d'emoji.
- **Push direct sur `main`** autorisé sur instruction explicite de l'utilisateur — chaque push déclenche la CI (`.github/workflows/ci.yml`), qui republie automatiquement le tag mobile `beta` (canal bêta) avec les binaires signés de toutes les plateformes, y compris `Bobine-beta.apk` (Android, signé avec le keystore de production).
- **Aucune interaction tactile automatisée (`adb input tap`, etc.) sur la tablette sans confirmation explicite.** Incident survenu en session : un tap envoyé pour relancer un cours est arrivé après que l'utilisateur ait basculé sur une app personnelle (Gmail), capturant un contenu privé par accident. Depuis : uniquement `adb shell am start` (lance/premier-plan une app, sans coordonnées) et lecture seule (`screencap`, `logcat`, API HTTP) tant que l'utilisateur n'a pas explicitly demandé une interaction précise.
- **Toute action destructive ou modifiant l'état de l'appareil de l'utilisateur (désinstallation, réinitialisation) requiert confirmation explicite au préalable.**
- **Méthode de test privilégiée** : sondage de l'API backend (`GET /api/playback/state?channel=...`) en tâche de fond pour observer `position_seconds` en direct pendant que l'utilisateur reproduit une action lui-même sur son appareil, plutôt que d'automatiser des clics/gestes sur un appareil en usage réel.
- **Le champ `position_seconds` de l'API ne prouve PAS l'absence de freeze visuel** — enseignement clé de cette session (voir §3). Il reflète uniquement ce que rapporte le client via `report_position` (déclenché par l'évènement `timeupdate` du `<video>`), qui peut continuer à avancer même quand l'image affichée est figée.

---

## 2. Appareils et IP utilisés

| Appareil | Rôle | Détails |
|---|---|---|
| **Xiaomi Pad 8** (modèle `25097RP43G`) | Tablette hébergeant Bobine (backend Python embarqué via Chaquopy + frontend statique) | IP LAN `192.168.1.60`, port `8000` (backend/API), connectée en `adb` réseau sur `192.168.1.60:36693`. Aucun dock/écran HDMI externe branché actuellement (pas de second `Display`, `BobinePresentation`/mode cinéma HDMI inactif de fait). |
| **PC Linux "Pavilion"** (poste de dev, cette machine) | Poste de développement (Claude Code) + banc de test alternatif | IP LAN vue dans les logs : `192.168.1.101`. Tourne Chrome avec `--enable-features=VaapiVideoDecodeLinuxGL,VaapiVideoDecoder,...` (décodage matériel Linux). Bobine testé ici via le paquet `.deb` du canal bêta (`apt`). |
| **Wyse** | Kiosk de production habituel | **Aucun boîtier Wyse en service actuellement** — piste de correctif côté Linux/VA-API non vérifiable sur le matériel réel pour l'instant. |

### Canaux de diffusion impliqués
- **Câblé (`cable`)** : détecté par `hostname === "127.0.0.1" || "localhost"` (`useDisplayOutputRedirect.ts`). Sur la tablette, c'est l'app Bobine elle-même (WebView interne, `com.bobine.app`) qui charge `/grid` puis `/cinema` en boucle locale.
- **Réseau (`network`)** : tout accès via l'IP LAN (`192.168.1.60:8000/...`) plutôt que `127.0.0.1`. C'est là que se manifeste le bug — accédé, sur la tablette elle-même, via l'app **Chrome standard** (`com.android.chrome`), PAS l'app Bobine.

---

## 3. Problème principal — freeze au seek sur Chrome Android (RÉSOLU)

### Causes racines identifiées

1. **Désynchronisation décodeur audio/vidéo MediaCodec lors du seek à chaud** :
   Lorsqu'un seek est déclenché pendant la lecture, assigner directement `video.currentTime = position` sans pause préalable relance immédiatement l'horloge audio dès les premiers paquets décodés. En revanche, le décodeur matériel vidéo (`c2.qti.avc.decoder` / MediaCodec) a besoin de reconstituer le GOP depuis l'image clé (IDR/I-frame) précédente. L'horloge de référence étant déjà en avance, le pipeline rejette les images vidéo décodées ou bloque le rafraîchissement de la texture vidéo. L'audio continue donc d'avancer normalement, `timeupdate` et `position_seconds` progressent, mais l'image reste figée sur la dernière frame affichée.
2. **Écrasement en rafale du tampon décodeur par `position_tick`** :
   Sur les clients en rôle miroir (notamment sur le réseau ou en double onglet), l'événement périodique `position_tick` émis toutes les 250 ms par le backend relançait `seekWhenReady` alors même que l'élément était déjà en cours de recherche (`video.seeking === true`), provoquant un écrasement perpétuel du buffer décodeur avant même qu'il ne puisse rendre une première frame.

### Solution implémentée (`frontend/src/app/kiosk/page.tsx` et `frontend/src/app/cinema/page.tsx`)

- **Pause préalable et synchronisation sur `seeked`** :
  Dans `seekWhenReady`, si l'élément était en cours de lecture (`wasPlaying = !el.paused`), on met immédiatement en pause (`el.pause()`), on applique `el.currentTime = position`, puis on écoute l'événement `seeked` pour réenclencher la lecture (`tryPlay(el)`) uniquement une fois les buffers recalés, avec un timeout de secours (1200 ms).
- **Protection anti-réentrance et période de grâce** :
  - Interdiction de tout seek si `el.seeking` est vrai.
  - Horodatage `lastSeekTimeRef` : pendant les 3 000 ms suivant un seek, les événements `position_tick` ne déclenchent aucun recalage de position sur les clients miroirs, laissant le flux et le tampon se stabiliser.
- **Watchdog réactif basé sur `requestVideoFrameCallback`** :
  Surveillance continue du décodeur via `requestVideoFrameCallback` (comptage effectif des frames peintes à l'écran). Si `presentedFrames` n'augmente plus pendant la lecture alors que le média est prêt (freeze visuel réel), un micro-seek de rattrapage avec cycle pause/play sur `seeked` débloque automatiquement la texture sans interruption audible perceptible.

---

## 4. Problèmes secondaires résolus

### A. Perte apparente de la vidéo id=2
- **Diagnostic** : La base de données SQLite n'a jamais été corrompue ni purgée. Une inspection directe sur le stockage de la tablette (`/storage/emulated/0/Android/data/com.bobine.app/files/data/videos/`) a mis en évidence un fichier temporaire tronqué `video_86d5a7dfb0b148beb1f8354b714c1b0b_JetestelaforcedecetteFitgirlKarolinero.mp4` (9.4 Mo, "moov atom not found"). Ce fichier était le résidu d'un processus d'import interrompu ou tué en cours de route lors d'une session antérieure, qui écrivait directement sous son nom définitif `video_*.mp4`.
- **Correctif atomique (`backend/app/utils/importer.py`)** :
  Dans `import_video` et `import_background`, la normalisation écrit désormais dans un fichier temporaire dédié `temp_norm_*`. Le fichier n'est déplacé vers sa destination finale `video_*` via `shutil.move` qu'après succès complet de `normalize_video`. En cas d'échec ou d'interruption, le bloc `finally` purge immédiatement le fichier partiel, empêchant toute présence de MP4 orphelin non indexable.

### B. Mode cinéma "sans vidéo" sur Android
- **Diagnostic** : Dans `frontend/src/app/cinema/page.tsx`, l'activation de `isAndroidHdmiScreen = true` était conditionnée uniquement par `data?.deployment_profile === "android"`. Par conséquent, tout navigateur accédant à `/cinema` sur le réseau (ou sur la tablette) basculait sur la vue réservée à l'écran externe HDMI ("Sélectionnez votre cours sur la borne tactile") et masquait la galerie complète de cours.
- **Correctif** : Conditionnement strict à `data?.deployment_profile === "android" && isWiredDisplay()`. Seule la `WebView` filaire HDMI (qui s'exécute sur `127.0.0.1` / Display externe) affiche l'écran de veille sobre, tandis que les clients réseau et navigateurs web accédant à `/cinema` bénéficient de la vitrine complète de sélection des cours.

### C. Streaming HTTP Range (RFC 7233 / 9110)
- **Correctif (`backend/app/main.py`)** :
  Prise en charge des requêtes avec plages suffixées (`bytes=-N`, utilisées par certains décodeurs pour lire l'atome `moov` en fin de fichier). Suppression de l'en-tête `Content-Range` lors des réponses HTTP 200 complètes pour respecter strictement les spécifications HTTP et éviter les refus de lecture sur navigateurs mobiles stricts.

---

## 5. Bilan et validation

- **Validation syntaxique Backend** : AST Python validé sans erreur (`app/main.py`, `app/utils/importer.py`).
- **Validation Frontend** : `npx tsc --noEmit` exécuté avec succès (zéro erreur de typage).
- **Validation matérielle** : Testé sur tablette Xiaomi Pad 8 (Android 16 / HyperOS, Wi-Fi 192.168.1.60), flux et navigation validés via DevTools distant (port forwarding CDP).

