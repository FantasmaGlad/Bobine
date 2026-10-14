<p align="center">
  <img src="../Assets/Images/firefox.svg" alt="Logo Firefox" width="96" />
</p>

# Plan d'implémentation — Support complet des navigateurs Firefox / Gecko

> **Statut (4.0.3)** : tous les lots **F0 à F8 sont livrés** ; **F4 et F6 avec des limites documentées** (voir §6 « Statut par lot » pour ce qui reste). Le ralentissement d'import signalé a été **identifié par le mainteneur comme une fuite mémoire d'un autre logiciel du poste concerné, étrangère à Bobine** (cohérent avec les mesures ci-dessous : aucun lag reproduit côté Bobine).
> **Origine** : signalement « crash / énorme lag lors de l'import de média dans la bibliothèque, surtout sur Firefox » et demande d'un support complet de Firefox pour l'interface d'administration **et** pour les lecteurs ouverts depuis d'autres appareils (ex. `/radio` depuis un poste tiers).
> **Principe** : Bobine soutient le projet Firefox et vise la même qualité sur tout navigateur moderne. Firefox est une marque de Mozilla Foundation ; son logo n'est utilisé ici que pour indiquer la compatibilité, sans affiliation ni parrainage.

---

## 1. Résumé

1. **Le crash/lag d'import signalé n'est pas imputable à Bobine** : le mainteneur l'a identifié comme une **fuite mémoire d'un autre logiciel tournant sur le poste concerné** (information du mainteneur, non mesurée ici). Cela concorde avec nos mesures : sur Firefox 157 (Linux, headless) rien n'a pu être reproduit, ni en local, ni à travers un lien limité à 32 Mbit/s, ni avec 31 fichiers / 1,5 Go. Le durcissement de l'import (§6) reste utile et livré, mais il ne répond pas à ce signalement. Le protocole du §5 est conservé pour un éventuel futur signalement.
2. Les **API et protocoles** utilisés par Bobine sont **tous présents** dans Firefox 157 (WebSocket, XHR upload, Range, Web Audio, Gamepad, Wake Lock, `requestVideoFrameCallback`, `webkitdirectory`…).
3. Trois **défauts réels** ont été trouvés et prouvés (§4.3) : `HEAD` sur les flux média qui renvoie du HTML, filtre MIME du glisser-déposer trop strict, et bibliothèque qui conserve HEVC/VP9/4K60 tels quels (lisibles ou non selon l'OS et le matériel du navigateur).
4. Le plan (§6) est découpé en **9 lots F0–F8**, chacun avec critères d'acceptation mesurables. Ils sont implémentés dans la version 4.0.3 (statut par lot en tête du §6) et vérifiés par un banc Firefox automatisé : 17 contrôles de bout en bout, dont la reprise d'un transfert après une coupure réseau.

---

## 2. Périmètre et politique de support

| Famille | Moteur | Cible |
|---|---|---|
| Firefox Bureau (Windows, macOS, Linux) | Gecko | **Release stable et N-1, plus la ESR courante** |
| Firefox pour Android | Gecko | Release stable (téléphone/tablette tiers, `/mobile`, `/radio`, `/kiosk`) |
| Dérivés (LibreWolf, Waterfox, Floorp, Zen) | Gecko | Support « au mieux » : même moteur, réglages de confidentialité différents (voir F6) |
| Tor Browser | Gecko | Hors périmètre en niveau « Plus sûr/Safest » (JavaScript/média désactivés) ; niveau « Standard » testé au lot F8 |
| Firefox pour iOS | **WebKit** (contrainte Apple) | Traité comme Safari, hors de ce plan |

Garde-fous : le serveur FastAPI et l'interface Next.js exportée restent **uniques** (aucune branche de code spécifique à un navigateur sauf détection de fonctionnalités, jamais `navigator.userAgent`). Le kiosque Chromium de l'appliance headless n'est pas modifié.

---

## 3. Méthode de mesure

- **Navigateur** : Firefox 157.0 (Linux, snap), piloté par geckodriver 0.37.1 en mode `-headless` (donc **sans accélération GPU**).
- **Backend** : instance isolée (données dans un dossier temporaire, sans mDNS), `frontend/out` de la branche courante.
- **Médias** : générés par `ffmpeg -f lavfi testsrc2` — H.264 720p 4 Mbit/s, 1080p 8 Mbit/s, 1080p 60 Mbit/s (190 Mo), HEVC Main10 4K60 (~40 Mbit/s), H.264 High10 1080p, MKV.
- **Instruments** : retard de boucle d'évènements (`setInterval` 25 ms), écarts de frames (`requestAnimationFrame`), `getVideoPlaybackQuality()`, RSS cumulé des processus Firefox, latence de `GET /api/health` sondée toutes les 250 ms.
- **Lien dégradé** : proxy TCP limitant le montant à 4 Mo/s (32 Mbit/s) + 30 ms de latence.
- Les outils sont versionnés dans [`scripts/browser-bench/`](../scripts/browser-bench/README.md) pour reproduire chaque chiffre ci-dessous.

---

## 4. Résultats

### 4.1 Import (téléversement) — aucun ralentissement imputable à Bobine

| Scénario | Résultat mesuré |
|---|---|
| 2 fichiers (10 Mo + 190 Mo), localhost | importés en ≈ 2 s ; retard de boucle max **3 ms** ; 0 écart de frame > 100 ms |
| 31 fichiers (6 × 190 Mo + 25 × 10 Mo = 1,5 Go), localhost, 3 transferts parallèles | terminé en ≈ 14 s ; retard de boucle max **28 ms**, frame max 50 ms ; RSS Firefox 1,5 → 1,1 Go (décroissant) |
| 3 × 190 Mo à travers 32 Mbit/s + 30 ms | ≈ 61 s ; retard de boucle max **4 ms** ; RSS stable ≈ 1,2 Go ; latence API max **20 ms** |
| Import 3 × H.264 High10 avec backend **et** Firefox limités à 2 cœurs | terminé en < 4 s ; latence API max 10 ms (un pic isolé de 9,7 s observé une seule fois pendant la 1re mesure, probablement le démarrage, non reproduit) |

Lecture du code : aucun fichier n'est lu en mémoire côté JavaScript (`FormData` + `XMLHttpRequest` référencent le `File` sur disque) ; `UploadManager.tsx` met à jour l'état React à **chaque** évènement `progress` (3 transferts), ce qui est sans effet mesurable ici mais constitue le premier point de coût sur un poste faible (lot F2).

### 4.2 Lecture — ce que Firefox décode

| Flux (lecture 8 s, essai isolé) | Images décodées | Perdues |
|---|---|---|
| H.264 720p 4 Mbit/s | 238 | 0 |
| H.264 1080p 8 Mbit/s | 238 | 0 |
| H.264 1080p 60 Mbit/s | 237 | 0 |
| HEVC Main10 4K60 | 472 | 42 (9 %) ; 0–2 sur deux essais ultérieurs |

Observation **non reproduite** : lors d'une première mesure, immédiatement après plusieurs encodages ffmpeg 4K qui saturaient les 16 threads, la lecture HEVC 4K60 a perdu 185/477 images avec un blocage de boucle de 1,5 s, puis un blocage de 26 s a été relevé à l'enchaînement sur un flux H.264. Deux essais de contrôle (machine au repos) n'ont montré aucun blocage. **Lecture** : le décodage logiciel 4K sur un poste chargé peut gêner l'interface ; à confirmer sur le poste du signalement (§5).

Matrice `canPlayType` (Firefox 157, Linux) : H.264 Baseline/High (dont L5.1), HEVC Main/Main10, AV1, VP9, VP8, AAC-LC, HE-AAC, MP3, Opus, FLAC, WAV, Vorbis → supportés ; **AC-3 et E-AC-3 → non supportés** (déjà recodés en AAC par l'importeur). **Le support HEVC/AV1 dépend de l'OS et du matériel** (Windows : extension « HEVC Video Extensions » ; Linux : build/pilote VA-API ; Android : décodeur matériel) — cette plateforme-ci n'est pas représentative de Windows.

### 4.3 Protocoles et API

| Sujet | Verdict | Détail |
|---|---|---|
| WebSocket `/ws/playback` | ✅ | Connexion, `boot_id`, filtrage de canal, reconnexion OK |
| `Range` sur `/api/videos/{id}/stream` | ✅ | `206` + `Content-Range` ; plage suffixe `bytes=-N` OK |
| CORS (`OPTIONS`) | ✅ | Origine LAN acceptée, méthodes complètes |
| **`HEAD` sur les `/stream`** | ❌ **défaut** | `HEAD /api/videos/{id}/stream` renvoie `206` avec `content-type: text/html` (la page 404 du frontend, 17 645 octets) au lieu des en-têtes média ; `HEAD /api/radio/tracks/{id}/stream` → 404. Cause : routes déclarées en `@app.get`, `HEAD` retombe sur le montage statique `/`. |
| **Glisser-déposer : filtre `f.type.startsWith("video/")`** | ⚠️ **défaut probable** | `File.type` est dérivé de l'OS : vide pour certaines extensions (`.mkv`, `.ts`, `.mov`, `.m4v`, `.avi`) selon Firefox/OS → fichiers ignorés **sans message** (le champ `accept="video/*"` du sélecteur n'a pas ce défaut). À confirmer par essai sur Windows/macOS. |
| **Bibliothèque conserve HEVC/VP9** | ⚠️ **limite de conception** | `COMPATIBLE_COURSE_VIDEO_CODECS` (liste blanche des cours) inclut HEVC et VP9 ; l'import fait seulement un `remux`/recodage audio/conteneur (vérifié : `hevc 4k60` importé en `codec: hevc`, 3840×2160). Ni profil, ni 10 bits, ni 4:2:2, ni 60 i/s ne sont contrôlés. |
| API utilisées | ✅ | `wakeLock`, `getGamepads`, `AudioContext`, `webkitdirectory`, `webkitGetAsEntry`, `caches`, `MediaSession`, Fullscreen, `requestVideoFrameCallback`, `ResizeObserver`, `BroadcastChannel`… présentes |
| API absentes de Firefox 157 | ℹ️ | `showDirectoryPicker` (non utilisé), `PerformanceObserver` `longtask`, `animation-timeline`, `interpolate-size`, `line-clamp` sans préfixe (le code utilise `-webkit-line-clamp`, supporté) |
| `deviceMemory` | ℹ️ | Non exposé par Firefox : ne jamais s'en servir pour adapter la charge |

> **Corrigés dans la 4.0.3** : `HEAD` sur les flux (F1), filtre MIME du glisser-déposer (F2), conservation de HEVC/VP9/10 bits sans repli pour les navigateurs qui ne les décodent pas (F3 : version web servie par négociation). Les mesures de ce chapitre décrivent l'état AVANT correction.

> **À vérifier au banc (F0)** — documenté mais pas encore mesuré ici : `wakeLock` et `getGamepads` exigent un **contexte sécurisé** (HTTPS ou `localhost`). Sur un poste tiers qui ouvre `http://bobine.local:8000`, ils sont donc attendus **absents**, y compris sous Chrome — à confirmer avec une mesure par IP LAN.

---

## 5. Protocole de diagnostic du signalement (à exécuter sur le poste concerné)

*Signalement d'origine résolu : fuite mémoire d'un autre logiciel du poste, hors Bobine.* Ce protocole reste valable pour tout nouveau signalement ; il permet de distinguer un défaut de Bobine d'un problème du poste. Demander, pour **un** crash/lag :

1. Version de Firefox et OS (`about:support` → *Copier les informations* ; mentionner ESR/release, RAM, GPU, « Décodage matériel »).
2. Où tourne le backend : **même machine que le navigateur** (app Windows/macOS/Linux) ou autre appareil ?
3. Fichiers : nombre, tailles, extensions, codecs (`ffprobe`), via **sélecteur** ou **glisser-déposer**.
4. Moment du lag : pendant le **transfert** (barre d'upload) ou pendant le **traitement** (« Réencodage… ») ou à l'**ouverture de la bibliothèque** après import.
5. Console (`Ctrl+Maj+K`) et onglet Réseau : requêtes en échec / en attente ; `about:crashes` pour l'identifiant de rapport si l'onglet plante ; `about:memory` → *Mesurer* pendant le lag.
6. Mêmes fichiers sous Chrome/Edge sur la même machine (le lag est-il spécifique à Firefox ?).
7. Charge CPU du **serveur** pendant le lag (`top` : processus `ffmpeg`).

Hypothèses qui étaient en discussion avant l'identification de la vraie cause (aucune n'a été démontrée ; la fuite mémoire d'un logiciel tiers du poste les explique toutes) :

| # | Hypothèse | Test discriminant |
|---|---|---|
| H1 | Fichier > 2 Go dans **une seule** requête multipart (mémoire/temp du navigateur ou limites intermédiaires) | Import d'un 3–5 Go, mesurer RSS Firefox et mémoire serveur |
| H2 | Backend et navigateur sur le même poste faible ; `ffmpeg -threads 0` sans priorité réduite (vérifié : `nice 0`) | Imposer `nice`/limite de threads, comparer |
| H3 | Décodage logiciel 4K/HEVC dans la bibliothèque (aperçu `<video preload="metadata">`) sur poste sans accélération | `media.hardware-video-decoding.enabled`, `about:support` |
| H4 | Mise à jour d'état React à chaque évènement `progress` × N transferts sur CPU faible | Profileur Firefox pendant l'upload |
| H5 | Limite de 6 connexions HTTP/1.1 par hôte (3 transferts + WebSocket + miniatures) sur lien lent | Onglet Réseau : requêtes « bloquées » |
| H6 | Extension (bloqueur, antivirus web) interceptant les gros `POST` | Profil Firefox vierge / mode sans échec |

---

## 6. Plan d'implémentation

### Statut par lot (version 4.0.3)

| Lot | État | Livré | Reste / non vérifié |
|---|---|---|---|
| F0 banc Gecko | **livré** | `scripts/browser-bench/e2e_firefox.py` (17 contrôles) + job CI `firefox-smoke` | Windows, macOS, Firefox pour Android et ESR non mesurés ; comparatif Chrome chiffré non fait |
| F1 HTTP des flux | **livré** | `HEAD`/`Range`/`If-Range`/`416`/`ETag` sur tous les `/stream`, 404 JSON sous `/api/*` (`app/utils/media_response.py`, 32 tests) | — |
| F2 import robuste | **livré** | filtre par extension avec message, progression limitée à 4 Hz, concurrence adaptative, **téléversement par morceaux reprenable** (`/api/uploads`, reprise vérifiée après coupure réelle), `ffmpeg` à priorité réduite sur les postes partagés | `multipart` conservé pour les pistes audio multiples (petits fichiers) ; transfert de plusieurs Go non mesuré sur matériel réel |
| F3 profil « lisible partout » | **livré** | détection (`decode:*` / `perf:*`), version web H.264 8 bits ≤ 1080p produite à la demande ou automatiquement, négociation `?accept=`, badge et bouton dans la bibliothèque | production **à la demande** (réglage « automatique » désactivé par défaut) ; pas de repli automatique sur erreur de lecture côté lecteur |
| F4 lecteurs tiers | **livré (limites documentées)** | recalage immédiat au retour d'un onglet masqué, relance du contexte audio suspendu (radio), repli propre sans Wake Lock/Gamepad (déjà en place) | autoplay : le geste reste exigé par le navigateur (rien à contourner) ; synchronisation ±300 ms après 30 min d'onglet masqué non mesurée |
| F5 diagnostic intégré | **livré** | Réglages → Compatibilité navigateur (formats, API, préférence de version, mesure de lecture 5 s, rapport copiable, conseils par OS) | décodage matériel non détectable de façon fiable par une API Web : seulement la mesure d'images perdues |
| F6 dérivés & confidentialité | **livré (limites documentées)** | aucune logique sur `performance.now()` fin/canvas ; `packaging/firefox/policies.json` (kiosque Firefox optionnel) | **HTTPS local optionnel non implémenté** ; `policies.json` non testé sur un Firefox réel (écriture système requise) ; LibreWolf/Tor Browser non testés |
| F7 outillage | **livré** | `browserslist` (Firefox ESR et courant, Chromium, Safari) + `eslint-plugin-compat` | — |
| F8 documentation | **livré** | README, ARCHITECTURE §10.3, notes 4.0.3, ce document | — |

Ordre recommandé : **F0 → F1 → F2 → F3 → F4 → F5 → F6 → F7 → F8**. F0 et F1 sont indépendants et peu risqués : à livrer en premier.

### F0 — Banc de test Gecko (prérequis)
- Promouvoir [`scripts/browser-bench/`](../scripts/browser-bench/README.md) en test reproductible : matrice Firefox ESR + stable, Windows/macOS/Linux/Android (BrowserStack ou machines physiques de la flotte).
- Ajouter au CI un job `firefox-smoke` (Playwright `firefox` ou geckodriver) : chargement de `/library`, `/radio`, `/kiosk?channel=network`, `/coach`, `/settings` sans erreur console ; upload de 2 fichiers de test ; lecture 5 s d'un H.264.
- Mesurer enfin les points « à vérifier » du §4.3 (contexte non sécurisé, `File.type`, HEVC Windows).
- **Acceptation** : le job échoue si une page lève une erreur JS ou si le retard de boucle d'évènements dépasse 200 ms pendant l'import de référence. *(Réalisé : le banc détecte l'overlay d'erreur Next.js et le retard de boucle ; les erreurs de console ne sont pas lisibles via WebDriver classique.)*

### F1 — Conformité HTTP des flux média (correctif prouvé)
- Fichiers : `backend/app/main.py` (routes `/stream`), tests `backend/tests/`.
- Répondre à **`HEAD`** sur `/api/videos|backgrounds|audio|radio/**/stream` avec les mêmes en-têtes que `GET` (`Content-Type` exact, `Content-Length`, `Accept-Ranges`, `Content-Range` si `Range`), sans corps ; ne jamais retomber sur le montage statique pour un chemin `/api/*`.
- `If-Range`, `416 Range Not Satisfiable` correct, `ETag`/`Last-Modified` sur les flux, `X-Content-Type-Options: nosniff`.
- **Acceptation** : `curl -I` et `curl -I -H "Range: bytes=0-99"` renvoient `video/mp4` ; tests pytest GET/HEAD/Range/suffixe/416 ; aucun chemin `/api/*` ne renvoie du HTML.

### F2 — Import robuste et économe (pose des correctifs H1, H4, H5 + filtre MIME)
- **Filtre de dépôt** : décider par **extension et contenu** (`ffprobe` côté serveur), pas par `File.type` ; message explicite pour tout fichier ignoré. Fichiers : `frontend/src/app/library/page.tsx` (+ pages audio/radio/fonds).
- **Progression** : sortir la progression du state React global (store externe + `useSyncExternalStore`, mise à jour ≤ 4 Hz) ; `UploadFloatingPanel` isolé.
- **Téléversement par morceaux reprenable** (8–16 Mo, `Blob.slice`, `Content-Range`/`Upload-Offset`) : supprime la dépendance à une requête multipart unique de plusieurs Go, permet la **reprise après coupure Wi-Fi**, réduit la pression mémoire (Firefox Android compris) et la limite de connexions (1 connexion active par fichier, réutilisée). Backend : écriture en flux dans `data/tmp`, vérification de l'espace disque **avant** d'accepter, renommage atomique.
- **Concurrence adaptative** : 3 → 1 transfert sur mobile/CPU faible (`navigator.hardwareConcurrency`, jamais `deviceMemory`).
- **Traitement serveur** : `ffmpeg` lancé avec priorité réduite (`nice 10` / `BELOW_NORMAL_PRIORITY_CLASS`, `ionice`) et plafond de threads sur les profils où le navigateur partage la machine (Windows/macOS/Linux de bureau, Android) ; inchangé sur l'appliance headless dédiée.
- **Acceptation** : import de 3 × 4 Go sans pic de RSS Firefox > 1,5 Go ni retard de boucle > 100 ms ; coupure réseau de 20 s pendant un transfert → reprise sans recommencer ; latence `GET /api/health` < 250 ms pendant un réencodage 4K sur 2 cœurs.

### F3 — Profil « lisible partout » et négociation de codec
- Définir un **profil web sûr** : H.264 High ≤ niveau 4.2, 4:2:0 8 bits, ≤ 1080p60 ou 4K30, AAC-LC stéréo/5.1, MP4 faststart. Étendre `analyze`/`is_compatible` (`backend/app/utils/video_utils.py`) pour contrôler profil, `pix_fmt`, niveau, cadence en plus du codec.
- Conserver l'original (sortie HDMI/kiosque local) et produire en tâche de fond, basse priorité, une **rendition web** pour les appareils tiers ; stocker la relation (champ `web_path`) et l'exposer par `GET /api/videos/{id}/stream?profile=web`.
- Côté client : `MediaCapabilities.decodingInfo()` + `canPlayType` pour choisir la rendition ; repli automatique sur la rendition web si `error.code == 4` ou si `smooth/powerEfficient` est faux.
- Badge dans la bibliothèque : « Lisible sur tous les navigateurs » / « Peut ne pas être lisible sur certains navigateurs ».
- **Acceptation** : HEVC Main10 4K60, High10 et VP9 importés sont lus sans perte d'images > 1 % sur un Firefox sans accélération matérielle ; les originaux restent inchangés.

### F4 — Lecteurs sur appareils tiers (`/radio`, `/kiosk`, `/cinema`)
- **Autoplay** : Firefox bloque par défaut l'audio audible sans geste — déjà géré par `/radio` (`unlocked`) et `/kiosk` réseau (bandeau « Activer le son ») ; unifier en un composant unique et **persister le geste** (`localStorage`) ; reprendre l'`AudioContext` sur `visibilitychange`/`onstatechange`.
- **Onglet en arrière-plan** : Firefox limite fortement les minuteurs (≥ 1 s, jusqu'à 1/min) → les suiveurs d'horloge serveur (`useVideoClockFollower`, `useAudioClockFollower`) ne doivent pas dépendre de `setInterval` pour rester synchrones ; s'appuyer sur `timeupdate`/`rVFC`/reprise à `visibilitychange`.
- **Contexte non sécurisé** : prévoir un repli propre quand `wakeLock`/`getGamepads` sont absents sur `http://<ip>` (message discret, jamais d'erreur) ; option HTTPS locale (AC locale optionnelle, F6).
- **`requestVideoFrameCallback`** (Firefox ≥ 132) avec repli `requestAnimationFrame`.
- **Acceptation** : `/radio` depuis Firefox sur un poste tiers démarre au premier clic, reste synchrone ±300 ms après 30 min d'onglet masqué, sans erreur console.

### F5 — Accélération matérielle et diagnostic intégré
- Page *Réglages → Compatibilité navigateur* : exécute `support-matrix` (version allégée), `MediaCapabilities` 1080p60/4K30/HEVC, mesure d'images perdues sur 5 s ; affiche « décodage matériel : oui/non/inconnu » et, si non, **conseils par OS** :
  - Firefox Linux : VA-API (`media.ffmpeg.vaapi.enabled`, vérifier `about:support` → *Media*), pilotes Mesa/`intel-media-va-driver`.
  - Firefox Windows : décodage matériel D3D11 ; HEVC = extension Microsoft.
  - Firefox macOS : VideoToolbox (automatique).
  - Firefox Android : décodeur matériel du SoC (MediaCodec).
- Bouton « Copier le rapport » (aucune télémétrie, rien n'est envoyé).
- **Acceptation** : le rapport s'affiche sur Chromium, Firefox, Safari sans erreur.

### F6 — Dérivés de Firefox et confidentialité
- LibreWolf/Tor Browser/`resistFingerprinting` : ne jamais baser une logique sur `performance.now()` fin, `canvas` ou `MediaCapabilities` (peuvent être dégradés/masqués) ; chemins de repli testés.
- HTTPS local optionnel (certificat d'une AC locale générée par l'assistant, installée par l'utilisateur) pour activer Wake Lock/Gamepad sur les postes tiers.
- Politique `policies.json` fournie pour un **kiosque Firefox** optionnel (autoplay autorisé, télémétrie désactivée, plein écran).
- **Acceptation** : `/radio` et `/library` fonctionnent sous LibreWolf (profil par défaut) et Tor Browser « Standard ».

### F7 — Compatibilité CSS/JS garantie par l'outillage
- `browserslist` explicite dans `frontend/package.json` (`firefox ESR`, `last 2 firefox versions`, Chromium/Safari actuels) ; `eslint-plugin-compat` ; Stylelint `no-unsupported-browser-features`.
- Revue des fonctionnalités récentes (`dvh`, `:has`, `color-mix`, `oklch`, `field-sizing`) : `@supports` + repli quand la ESR ne les gère pas.
- **Acceptation** : build échoue si une fonctionnalité hors `browserslist` est utilisée sans repli.

### F8 — Documentation, communication, non-régression
- README (EN/FR) : badge et section **Browser support** avec logo Firefox ; `docs/ARCHITECTURE*.md` §10.3 ; ce plan tenu à jour (statut par lot) ; note de version.
- `AGENTS.md` : règle « toute modification du frontend ou des flux média passe le banc Gecko (F0) ».
- Notice de marque : « Firefox est une marque de Mozilla Foundation — usage descriptif de compatibilité, aucune affiliation ».
- **Acceptation** : documentation FR/EN à jour, banc intégré à la checklist de release.

---

## 7. Risques et limites de cette étude

- Une seule plate-forme mesurée (Firefox 157, Linux, headless, sans GPU) ; Windows, macOS et Firefox Android **non mesurés**.
- Médias synthétiques ; la charge réelle du signalement (formats, tailles, nombre de cours en bibliothèque) peut différer.
- Le lag « surtout sur Firefox » n'a **pas** été retrouvé dans Bobine ; le mainteneur l'a rattaché à une fuite mémoire d'un autre logiciel du poste.
- Aucun comparatif Chrome chiffré n'a été exécuté ; il est prévu en F0 pour confirmer ou infirmer le caractère spécifique à Firefox.
