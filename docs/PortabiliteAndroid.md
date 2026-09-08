# Cahier des charges & Faisabilité — Portabilité Android (Bobine sur Tablette)

> Document de référence pour le portage de Bobine sur l'écosystème Android (tablette dédiée avec sortie HDMI filaire). Opérationnalisé par [`docs/plan-implementation-android.md`](plan-implementation-android.md), qui découpe ce cahier des charges en lots concrets et séquencés.

Matériel pilote actuellement en main : **Xiaomi Pad 8 (édition développeur), Android 16**. Le Lot 1 du plan d'implémentation valide la checklist matérielle (§6) contre cet appareil réel avant tout achat supplémentaire.

> **Lot 0 exécuté pour de vrai, GO confirmé (2026-09-08)** — le plan d'implémentation a été testé contre un vrai SDK Android, pas seulement planifié. Découverte majeure en cours de route : **`pydantic-core` (donc Pydantic v2, donc FastAPI) n'a aucune distribution Android fonctionnelle** — le résolveur pip installait silencieusement un paquet placeholder vide de 2022 au lieu de la vraie librairie, sans erreur visible. **Décision actée et validée par un build APK complet réussi** : downgrade vers Pydantic v1 (pur Python, sans extension native) + FastAPI 0.99.1, **uniquement sur le profil Android** — les autres plateformes gardent FastAPI/Pydantic v2 inchangés. Le reste de la stack (`sqlalchemy`, `alembic`, `apscheduler`, `pillow`, `psutil`, `pystray`, `zeroconf`, `uvicorn` sans `[standard]`) fonctionne, avec des ajustements mineurs de version. Seul `watchdog` reste un point ouvert sans solution trouvée. Détail complet, log exact et périmètre de compatibilité Pydantic v1 dans le code en §3.1 et dans les Découvertes du Lot 0 ([`docs/plan-implementation-android.md`](plan-implementation-android.md)).

---

## 1. Vision & Cas d'Usage

Dans l'architecture historique, Bobine nécessite un mini PC x86-64 (ex. Dell Wyse 5070 ou mini PC de salon) connecté en HDMI à l'écran de la salle, administré depuis un smartphone ou un PC distant sur le réseau local.

**La vision Android** : transformer une tablette Android moderne en une station autonome complète via un **seul fichier APK**, connectée à un **dock USB-C avec alimentation Power Delivery et sortie HDMI** :

1. **Écran tactile de la tablette** : affiche `/kiosk` (l'interface tactile de sélection d'un cours par l'adhérent — grille de cours, écran d'attente). La tablette **n'est pas verrouillée en mode kiosque** : elle démarre en plein écran immersif quand l'app Bobine est ouverte, mais un geste système standard (Accueil, multitâche) permet à tout moment de la quitter et d'utiliser la tablette pour autre chose — voir §4.
2. **Sortie HDMI du dock** : affiche `/cinema` (le lecteur plein écran) en 1080p/4K avec décodage matériel via `MediaCodec` — c'est la « sortie classique » du canal câblé, servie en interne par `http://127.0.0.1:8000/cinema`, exactement comme aujourd'hui sur mini PC x86.
3. **Interface admin** : accessible comme une page web ordinaire depuis la tablette (onglet dans l'app, ou navigateur), **sans verrouillage ni authentification dédiée** — le réseau local reste la seule barrière, comme aujourd'hui. Une authentification admin est une piste explorée pour plus tard, volontairement écartée du périmètre initial pour ne pas ajouter de friction.
4. **Serveur Backend autonome** : la tablette héberge elle-même FastAPI + SQLite et publie `bobine.local` sur le Wi-Fi de la salle, via un service d'arrière-plan qui **survit à la fermeture complète de l'app** (§4) — le cours continue de jouer sur le vidéoprojecteur même si quelqu'un ferme l'app par erreur ou emprunte la tablette pour un autre usage.

Ce document remplace la version précédente sur plusieurs points actés depuis (voir §2) : le rôle précis de l'écran tactile (sélection, pas administration), l'absence de verrouillage kiosque réel, la correction de l'approche FFmpeg, et le choix explicite de ne pas utiliser Kotlin Multiplatform.

---

## 2. Décisions actées (source de vérité)

Tableau récapitulatif des choix structurants, pour éviter de les re-débattre à chaque lot du plan d'implémentation.

| Sujet | Décision | Pourquoi |
|---|---|---|
| **minSdk / targetSdk** | API 34-36 (Android 14-16), pas de compatibilité descendante visée | Priorité donnée à l'avenir : les tablettes Android vieillissent moins bien qu'un mini PC headless, mieux vaut cibler les API récentes (Device Owner, DisplayManager et sécurité plus robustes) que la compatibilité avec du matériel ancien |
| **Moteur de rendu web** | WebView système Android (Chromium, mis à jour par Google Play Services) | Léger, zéro maintenance, cohérent avec le kiosque Linux actuel qui utilise déjà le Chromium du système d'exploitation |
| **Kotlin Multiplatform vs natif séparé** | **Kotlin natif pur pour Android.** Pas de KMP, y compris en prévision d'un futur port iOS | La logique métier partageable vit déjà dans le backend Python et le frontend Next.js, indépendamment du langage natif. La couche native restante diverge presque totalement entre Android (Chaquopy/JNI, `Presentation`/`DisplayManager`) et iOS (embarquement Python différent, `UIWindowScene`, modèle d'exécution en arrière-plan radicalement plus restrictif — cf. [`docs/PortabiliteIPadOS.md`](PortabiliteIPadOS.md) §4.A qui envisage même une architecture différente côté iOS). KMP n'aurait rien à partager que Python/TS ne partagent déjà |
| **Signature & distribution APK** | Auto-signé, publié en téléchargement direct sur GitHub Releases | Même posture que les `.exe`/`.dmg` actuels : pas de compte développeur, pas de revue de store. L'utilisateur autorise « sources inconnues » à l'installation |
| **Mapping des routes** | `/kiosk` sur l'écran tactile de la tablette, `/cinema` sur la sortie HDMI | L'adhérent choisit son cours au toucher sur la tablette ; la vidéo elle-même est projetée sur l'écran de la salle |
| **Verrouillage de l'écran tactile** | **Pas de Lock Task / mode kiosque réel.** Plein écran immersif (barres système masquées) au lancement de l'app, mais quittable à tout moment par un geste standard Android | La tablette doit rester utilisable pour autre chose — ce n'est pas un poste dédié comme le mini PC headless |
| **Device Owner** | Activé, **sans** Lock Task associé — uniquement pour l'exemption des restrictions batterie/OEM agressives (HyperOS, One UI) qui tuent les services en arrière-plan malgré l'exemption standard « ignorer l'optimisation de la batterie » | La survie du service en fond est le vrai risque opérationnel identifié (§7) ; Device Owner sans Lock Task obtient cette fiabilité sans sacrifier l'usage libre de la tablette |
| **Persistance du service d'arrière-plan** | Le `ForegroundService` (backend Python + `Presentation` HDMI) **continue de tourner même si l'app Bobine est fermée complètement** depuis le multitâche | Un swipe accidentel dans le multitâche, ou l'usage de la tablette pour autre chose, ne doit pas couper la diffusion HDMI en pleine séance |
| **Authentification admin** | Aucune pour l'instant — le réseau local reste la seule barrière, comme aujourd'hui sur mini PC | Priorité donnée au zéro-friction pour les admins ; piste explorée pour plus tard si l'exposition sur une tablette manipulable pose un problème réel en usage |
| **UI native de l'app** | Une vraie app avec sa propre interface (pas juste un raccourci Chrome), qui réplique le site web à l'identique | Expérience plus intégrée pour un studio : icône dédiée, notification persistante « Bobine actif », pas de dépendance à un navigateur tiers qui pourrait être tué indépendamment du service |
| **Mise à jour de l'app** | Vérification + téléchargement **in-app**, dans l'esprit du système Stable/Bêta desktop existant (`docs/ARCHITECTURE.md` §7) | Cohérent avec le choix « zéro friction » déjà fait pour l'admin ; nécessite `REQUEST_INSTALL_PACKAGES` (§8) |
| **Génération vidéo (vignettes, analyse)** | Binaire `ffmpeg`/`ffprobe` statique ARM64 embarqué, invoqué en `subprocess` **exactement comme aujourd'hui** — pas de `ffmpeg-kit-android` | Corrige une erreur de la version précédente de ce document (§9) : `ffmpeg-kit` est une librairie Java/Kotlin, pas un binaire qu'on invoque en ligne de commande, et son statut de maintenance est incertain (à vérifier avant tout engagement dessus) |
| **Tablette pilote** | Xiaomi Pad 8 (édition développeur), Android 16 — déjà en possession | Permet de commencer les lots de validation matérielle (§6, Lot 1 du plan) sans attendre un achat |

---

## 3. Architecture 100% Autonome (Sans Termux)

Pour un déploiement professionnel en salle de sport, **aucun terminal, script ou outil tiers (comme Termux) n'est acceptable**. L'utilisateur installe un fichier `Bobine.apk` unique, l'ouvre, et le système est opérationnel.

```
┌─────────────────────────────────────────────────────────────┐
│                       Bobine.apk                            │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │   Android Native Layer (Kotlin / Android Jetpack)     │  │
│  │                                                       │  │
│  │   ┌─────────────────────┐   ┌──────────────────────┐  │  │
│  │   │  ForegroundService  │   │   DisplayManager     │  │  │
│  │   │  (survit à la       │   │   & Presentation      │  │  │
│  │   │   fermeture de      │   │   (sortie HDMI)       │  │  │
│  │   │   l'app, §7)        │   │                       │  │  │
│  │   └──────────┬──────────┘   └──────────┬───────────┘  │  │
│  └──────────────┼─────────────────────────┼──────────────┘  │
│                 │                         │                 │
│  ┌──────────────▼──────────┐   ┌──────────▼──────────────┐  │
│  │ Chaquopy (CPython 3.11) │   │   Deux Vues Découplées  │  │
│  │                         │   │                         │  │
│  │ • FastAPI + Uvicorn     │   │ 1. Tablette : /kiosk     │  │
│  │ • SQLite (database.db)  │   │    (WebView, plein écran │  │
│  │ • APScheduler, zeroconf │   │     immersif, quittable) │  │
│  │ • ffmpeg/ffprobe ARM64  │   │ 2. HDMI : /cinema        │  │
│  │   statique (§9)         │   │    (Presentation, 4K)    │  │
│  └─────────────────────────┘   └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Cœur Backend : Chaquopy (CPython embarqué)

- **Chaquopy** est le SDK standard pour exécuter Python au sein d'une application Android native. L'interpréteur CPython et les paquets purs de `backend/requirements.txt` (`fastapi`, `uvicorn`, `sqlalchemy`, `apscheduler`, `zeroconf`, `watchdog`, `aiofiles`, `pillow`) sont intégrés directement dans l'APK.
- **Risque de compatibilité, VALIDÉ EMPIRIQUEMENT (Lot 0 du plan exécuté le 2026-09-08, pas seulement planifié)** :
  - **`pydantic-core` (extension Rust, dépendance dure de Pydantic v2 → FastAPI) N'A AUCUNE distribution Android fonctionnelle — bloquant confirmé, pas une hypothèse.** Le résolveur pip cross-cible de Chaquopy installe silencieusement `pydantic-core==0.0.1`, un paquet **placeholder vide publié en 2022** par l'auteur de Pydantic (« Placeholder until pydantic-core is released », aucun code réel) — le seul wheel jamais publié sous ce nom au format indépendant de plateforme, donc le seul visible pour Android, alors que toutes les vraies versions (2.x, l'extension Rust compilée réellement utilisée) sont taguées par plateforme desktop et invisibles pour cette cible.
  - **Décision actée et validée par build réel ET par exécution réelle sur émulateur : downgrade Pydantic v1 sur le profil Android uniquement.** `pydantic==1.10.26` (vraie librairie pure Python, testée) + `fastapi==0.99.1` (dernière version encore compatible Pydantic v1) — `app.main` démarre et sert `/kiosk` en HTTP 200 avec cette combinaison, vérifié visuellement (Lot 2). **Périmètre de compatibilité réel dans le code — corrigé après exécution, plus large que la première estimation par grep (3 points) faite au Lot 0** : la vraie liste, mesurée en faisant tourner `app.main` pour de vrai puis en élargissant le grep, compte **18 points** sur 8 fichiers :
    - `pydantic_settings.BaseSettings` → `pydantic.BaseSettings` intégré ([`config.py:6`](../backend/app/config.py)).
    - `field_validator` → `validator` ([`radio_announcements.py:20,75`](../backend/app/routers/radio_announcements.py)).
    - `.model_dump()` → `.dict()` ([`settings.py:339`](../backend/app/routers/settings.py)).
    - `.model_fields` → `.__fields__` ([`config.py:312`](../backend/app/config.py)).
    - `.model_fields_set` → `.__fields_set__` ([`radio.py:227`](../backend/app/routers/radio.py), [`radio_announcements.py:191`](../backend/app/routers/radio_announcements.py)).
    - `from_attributes = True` (nom v2 de l'ancien `orm_mode` v1, sans lequel la construction de `response_model` depuis un objet SQLAlchemy échoue) dans **14 `class Config`** à travers 6 fichiers (`videos.py`, `audio_playlists.py`, `playlists.py`, `backgrounds.py`, `audio.py`, `logs.py`) — corrigé en ajoutant `orm_mode = True` à côté (Pydantic v2 accepte cette clé comme alias legacy, avertissement de dépréciation seulement, pas d'erreur).
    - `computed_field` ([`backgrounds.py`](../backend/app/routers/backgrounds.py), propriété calculée `is_image`) — le seul point sans équivalent direct en v1, résolu par un petit module partagé [`backend/app/utils/_pydantic_compat.py`](../backend/app/utils/_pydantic_compat.py) (no-op + mixin de sérialisation sur v1, sans effet sur v2).
    - Tous corrigés avec le même schéma `try/except ImportError` (ou `getattr` de repli) déjà utilisé pour les 3 premiers points — **un seul `backend/app/` partagé entre profils, aucun fichier dupliqué**, 32/32 tests desktop toujours au vert après chaque changement. Détail complet, logs `adb logcat` et code exact dans les Découvertes du Lot 2 ([`docs/plan-implementation-android.md`](plan-implementation-android.md)).
  - **Compromis assumé** : le profil Android reste figé sur ce millésime FastAPI/Pydantic (mi-2023) tant qu'aucune distribution Android de `pydantic-core` n'existe — voir §10 pour la voie de retour possible vers Pydantic v2.
  - `psutil` (extension C, [`backend/app/main.py:159`](../backend/app/main.py) et [`backend/app/routers/settings.py:328`](../backend/app/routers/settings.py)) — **résolu, pas de risque** : une version Android existe (`7.1.3`, contre `7.2.2` sur desktop), simple ajustement de pin.
  - `pillow` et `zeroconf` avaient la même incertitude initiale non documentée dans la version précédente de ce CDC — **résolus** eux aussi avec un pin Android différent (`pillow==11.0.0`, `zeroconf==0.39.4` — cette dernière avec un écart de version notable par rapport au desktop, point de vigilance pour le Lot mDNS).
  - **Découverte supplémentaire, imprévue** : `watchdog` (surveillance du dossier d'import) **n'a aucune distribution Android du tout** — voir §9, point encore ouvert. `uvicorn[standard]` échoue aussi (son extra `httptools` n'a pas de wheel Android) — corrigé en utilisant `uvicorn` sans extra.
  - **Correction importante à ce compromis (Lot 3) : `uvicorn[standard]` ne fournit pas QUE l'accélération HTTP (`httptools`/`uvloop`), il fournit aussi le support WebSocket.** En retirant l'extra sans le remplacer, `/ws/playback` — le mécanisme central de synchronisation temps réel de Bobine (état de lecture, admin, télécommandes) — répondait `404 Not Found` avec `"No supported WebSocket library detected"`. C'était une vraie régression fonctionnelle, pas juste une perte de performance comme envisagé au Lot 0. **Corrigé** : `install("websockets")` ajouté séparément (résout proprement pour Android, sans `httptools`/`uvloop`), validé par une vraie connexion WebSocket de test recevant l'événement `boot_id` attendu.
  - **Verdict global du Lot 0 : GO**, confirmé par un APK complet généré avec succès (`android/app/build/outputs/apk/debug/app-debug.apk`).
- Au lancement de l'application, le `ForegroundService` (§7) instancie le thread Python et exécute :
  ```python
  uvicorn.run("app.main:app", host="0.0.0.0", port=8000, workers=1)
  ```
- `backend/app/desktop/tray.py` (point d'entrée séparé, PyInstaller pour les profils desktop) n'est **pas** concerné par ce portage : ce module n'est jamais importé par `app.main`, donc rien à en retirer pour Android.

### 3.2 Gestion Double Écran : `android.app.Presentation`

Android gère nativement le multi-affichage via [`DisplayManager`](https://developer.android.com/reference/android/hardware/display/DisplayManager) — ce n'est pas une recopie d'écran (mirroring compressé), c'est le mécanisme standard utilisé par Chromecast/Android Auto pour du contenu réellement indépendant sur un second écran :

- Dès que le câble HDMI est branché sur le dock USB-C, Android émet `DisplayListener.onDisplayAdded(displayId)`.
- L'application instancie une classe héritant de `android.app.Presentation(context, display)` qui charge `http://127.0.0.1:8000/cinema` — cette URL en `127.0.0.1` est un choix délibéré, pas cosmétique (§4).
- L'écran tactile de la tablette charge `/kiosk` via un hostname **différent** de `127.0.0.1` (§4) dans sa propre `WebView`, indépendamment de la `Presentation`.
- Si aucun écran externe n'est détecté, la tablette peut afficher `/cinema` à la place, avec un bouton de bascule rapide dans l'UI native.

### 3.3 Décodage Vidéo Matériel

- Le rendu du `<video>` HTML5 dans la `WebView` exploite automatiquement `MediaCodec` (décodeurs matériels du SoC) pour H.264 et H.265 (HEVC) en 4K, sans effort d'intégration.
- **Nuance à ne pas perdre** : le décodage matériel **AV1** dépend fortement du SoC — les Snapdragon 870 (référence historique de la checklist §6) n'ont généralement pas de décodeur AV1 matériel ; seuls les SoC très récents (8 Gen 2 et plus) l'ont. Sans impact pratique connu si le catalogue de cours reste en H.264/HEVC (cas des vidéos de cours filmées), mais à ne pas promettre comme un acquis universel.

---

## 4. Le point de vigilance : routage `/kiosk` vs `/cinema` par hostname

Le frontend distingue aujourd'hui « écran câblé » de « écran réseau » **uniquement par le hostname de la requête** — mécanisme existant, à ne pas casser ni dupliquer par erreur :

- [`frontend/src/lib/useDisplayOutputRedirect.ts`](../frontend/src/lib/useDisplayOutputRedirect.ts) : `isWiredDisplay()` (ligne 12-15) renvoie vrai uniquement si `window.location.hostname` vaut `127.0.0.1` ou `localhost`. Un appareil « câblé » suit toujours le réglage `cableOutput` choisi par l'admin et démarre directement dans le bon mode au boot ; un appareil « réseau » n'est redirigé que si l'admin bascule le réglage en direct pendant que la page est ouverte (comportement voulu : quelqu'un qui ouvre `/cinema` volontairement y reste).

**Implication pour le portage** : si la `Presentation` HDMI charge `http://127.0.0.1:8000/cinema`, elle hérite automatiquement de ce comportement existant sans aucun changement frontend — elle suit le réglage `cableOutput` de l'admin. C'est le comportement voulu (§1, sortie HDMI = « sortie classique »).

En revanche, la `WebView` de l'écran tactile **ne doit pas** aussi tourner sur `127.0.0.1`, sinon elle serait elle aussi classée « câblé » et suivrait le même réglage — cassant l'indépendance entre « ce que l'adhérent sélectionne au toucher » et « ce qui joue à l'écran ».

**Tranché et validé (Lot 3 du plan, exécuté) : `http://127.0.0.2:8000/kiosk/`**, ni `bobine.local` ni l'IP LAN de la tablette comme envisagé initialement. Le bloc entier `127.0.0.0/8` est loopback — n'importe quelle adresse de ce bloc atteint le même serveur local que `127.0.0.1`, mais `isWiredDisplay()` (comparaison de chaîne stricte) classe automatiquement `127.0.0.2` comme « réseau », **sans modifier une ligne de `useDisplayOutputRedirect.ts`**. Confirmé fonctionnel dans une vraie `WebView` Android (pas seulement testé au niveau TCP) : pas d'erreur `ERR_CLEARTEXT_NOT_PERMITTED`, pas de configuration de sécurité réseau Android supplémentaire nécessaire. Avantage décisif sur les deux options initialement envisagées : **aucune dépendance au Lot 8 (mDNS) ni à l'état du Wi-Fi** — fonctionne de façon identique que la tablette soit connectée ou non, dès le premier démarrage.

---

## 5. Réseau, Découverte & Alimentation

### 5.1 Port d'écoute & Découverte mDNS (`bobine.local`)

- **Port 8000** : Android autorise les sockets TCP non privilégiés (> 1024) sans root.
- **Résolution mDNS** : pour que les smartphones du personnel se connectent via `http://bobine.local:8000`, l'application acquiert un `MulticastLock` :
  ```kotlin
  val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as WifiManager
  val multicastLock = wifiManager.createMulticastLock("bobine_mdns_lock")
  multicastLock.setReferenceCounted(true)
  multicastLock.acquire()
  ```
  Le module Python `zeroconf`, déjà une dépendance du backend (`backend/requirements.txt`), peut alors émettre et recevoir librement les annonces réseau — aucun changement côté Python.

### 5.2 Stockage des Médias & Vidéos

- Stockage applicatif étendu : `context.getExternalFilesDir(null)` (type `/sdcard/Android/data/com.bobine.app/files/data/videos/`) — espace de plusieurs Go sans permission Android intrusive.
- Support du stockage externe USB OTG : import de cours directement via un port USB-A du dock.

---

## 6. Prérequis Matériels

| Composant | Exigence minimale | Exemples | Modèles incompatibles |
|---|---|---|---|
| **Port USB-C** | USB 3.2 Gen 1 avec DisplayPort Alt Mode | Xiaomi Pad 6/7/8, Samsung Galaxy Tab S7-S10 | Xiaomi Redmi Pad (USB 2.0), Xiaomi Pad 5 standard (USB 2.0), Lenovo Tab M10 (USB 2.0) |
| **SoC / Processeur** | Décodage matériel H.264/HEVC 4K60 fluide | Snapdragon 870 et supérieur | SoC d'entrée de gamme sans décodage HEVC 60fps fluide |
| **Stockage** | 128 Go ou 256 Go UFS | — | 32/64 Go eMMC |
| **Dock USB-C** | HDMI 4K@60Hz + USB-C PD (≥ 45W) + ports USB-A | Docks Anker, Ugreen, Baseus avec entrée secteur PD 65W | Adaptateurs simples sans injection de courant |

La tablette actuellement en main (Xiaomi Pad 8, édition développeur, Android 16) doit être validée contre cette checklist en tout premier lieu (Lot 1 du plan) — en particulier la négociation DisplayPort Alt Mode avec le dock réellement utilisé, qui varie selon le chipset du hub et n'est pas garantie par la seule fiche technique de la tablette.

---

## 7. Fonctionnement Continu 24h/24

- **Survie du service** : `ForegroundService` avec notification persistante (« Bobine diffuse en arrière-plan »), qui **survit à la fermeture complète de l'app** (§2) — découplé du cycle de vie de l'`Activity` UI.
- **Exemption batterie** : Device Owner **sans** Lock Task (§2) — obtient l'exemption des restrictions OEM agressives (HyperOS Xiaomi, One UI Samsung) qui tuent les services en arrière-plan même avec `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` accordé au niveau système. C'est un problème distinct et plus sérieux que le simple plafonnement de charge (point suivant), largement documenté sur les tablettes Android déployées en kiosque.
  - **Contrainte de provisioning à documenter** : `adb shell dpm set-device-owner com.bobine.app/.DeviceAdminReceiver` exige une tablette **vierge** (aucun compte Google, aucune app déjà configurée). Ça doit faire partie du provisioning initial de chaque tablette, pas d'une installation a posteriori sur un appareil déjà en service.
- **Plein écran immersif quittable** : au lancement, l'app masque les barres système (`WindowInsetsController`) mais un geste standard Android (Accueil, multitâche) reste actif — **pas** de Lock Task (§2).
- **Protection de la batterie** : sur les tablettes Xiaomi (HyperOS) et Samsung (One UI), activer la fonction native de plafonnement de charge à 80% pour préserver la batterie lors d'un branchement 24/7 sur secteur — sujet distinct de la survie du service ci-dessus, à ne pas confondre.

---

## 8. Mise à jour de l'application

Dans le même esprit que le système Stable/Bêta desktop existant ([`docs/ARCHITECTURE.md`](ARCHITECTURE.md) §7) : vérification et téléchargement **in-app**, pas de simple lien vers GitHub Releases à installer manuellement.

- L'app interroge périodiquement une URL de version (à définir : probablement le même mécanisme que `routers/updates.py` côté desktop, ou un endpoint dédié).
- Si une nouvelle version est disponible, l'app télécharge le nouvel APK et déclenche son installation via `REQUEST_INSTALL_PACKAGES` (permission spéciale, à demander explicitement — l'app étant hors Play Store, l'installation d'un APK par une autre app nécessite cette autorisation).
- Canal Stable / Bêta à envisager en miroir du desktop, sans obligation de parité totale dès le premier lot.

---

## 9. Ce que ce document corrige par rapport à sa version précédente

- **`ffmpeg-kit-android` remplacé par un binaire statique bundlé.** L'ancienne version proposait `ffmpeg-kit-android` « accessible depuis Python via `ctypes` ou liaison JNI » — formulation qui mélangeait deux approches incompatibles (`ffmpeg-kit` est une librairie Java/Kotlin avec une API programmatique, pas un exécutable qu'on invoque en ligne de commande). Le code actuel ([`backend/app/utils/video_utils.py`](../backend/app/utils/video_utils.py), [`backend/app/utils/radio_utils.py`](../backend/app/utils/radio_utils.py)) fait du pur `subprocess.run(["ffmpeg", ...])`/`["ffprobe", ...]`. La correction retenue (§2) : bundler un binaire statique ARM64 au format `lib*.so` dans `jniLibs/` (contrainte Android 10+ : interdiction d'exécuter un binaire natif hors du répertoire natif de l'app) et le pointer via `subprocess`, **sans changer une ligne du code Python existant**. `ffmpeg-kit` a par ailleurs un statut de maintenance incertain à vérifier avant tout engagement dessus.
- **Kotlin Multiplatform explicitement écarté** (§2), après examen — n'était pas mentionné dans la version précédente.
- **Le rôle des deux écrans a changé** : la version précédente plaçait l'admin sur l'écran tactile et `/kiosk` ou `/cinema` sur HDMI. La version actuelle place `/kiosk` (sélection tactile) sur la tablette, `/cinema` sur HDMI, et l'admin comme une page accessible librement sur la tablette — pas verrouillée dessus.
- **Le mode kiosque strict (Device Owner + Lock Task) est écarté** au profit d'un plein écran immersif quittable + Device Owner sans Lock Task uniquement pour l'exemption batterie.
- **Le ton général sur Chaquopy et les dépendances a changé, dans les deux sens.** La version précédente exprimait une incertitude générale non vérifiée (« CPython 3.11 embarqué », risque flou sur `pydantic-core`/`psutil`). Après exécution réelle du Lot 0 : Chaquopy est activement maintenu (v17.0, Python jusqu'à 3.14) — meilleure nouvelle que prévu — mais **`pydantic-core` s'est révélé être un vrai blocage confirmé** (pas juste un risque), tandis que `psutil` — présenté comme le principal doute — s'est avéré sans problème. Le § 3.1 documente maintenant des faits vérifiés, pas des suppositions.
- **« Le code Python de service des statics ne doit pas être modifié » (Lot 2) s'est révélé inexact.** Chaquopy monte le contenu de `chaquopy.sourceSets` sous un chemin fixe (`AssetFinder/app/...`) non configurable, incompatible avec la logique existante de `main.py` (3 `.parent` pour retrouver `frontend/out` en sibling de `backend/`). Une branche Android explicite, détectée via `hasattr(sys, "getandroidapilevel")`, a dû être ajoutée — petite, cohérente avec le style déjà en place (le fichier avait déjà des branches Windows/macOS/Linux), mais bien un changement de code, pas juste un ajustement de configuration.

---

## 10. Voie de retour possible vers Pydantic v2 (rapport prospectif)

Le downgrade Pydantic v1 (§2, §3.1) est un contournement délibéré, pas une position de principe — cette section documente à quelles conditions il redeviendrait inutile, pour qu'un futur agent ou mainteneur sache quoi vérifier plutôt que de redécouvrir le problème depuis zéro.

### 10.1 Pourquoi le blocage existe (rappel technique précis)

`pydantic-core` est une extension **Rust** (compilée via [PyO3](https://pyo3.rs)/[maturin](https://www.maturin.rs)), pas du Python pur — contrairement à `pydantic` lui-même (la couche Python au-dessus). Publier un paquet Python avec une extension native pour une plateforme donnée exige un *wheel* compilé et tagué pour cette plateforme précise (ABI, architecture). Au moment du Lot 0, **aucun wheel `pydantic-core` tagué pour Android n'existe** sur PyPI ni sur l'index Chaquopy — la seule version visible par un résolveur pip ciblant Android est un placeholder vide de 2022, sans rapport avec la vraie librairie.

Ce n'est pas propre à Chaquopy ou à Bobine : c'est un problème d'écosystème plus large. Android comme cible de compilation Python officielle (CPython lui-même le supporte nativement — c'est ce qui permet à Chaquopy d'exposer `sys.getandroidapilevel()`, utilisé §9) est une évolution récente ; l'écosystème des paquets à extension native (dont tout ce qui s'appuie sur PyO3/maturin, Cython, ou des liaisons C directes) suit avec du retard, au rythme où chaque mainteneur de paquet décide (ou non) de publier des wheels Android.

### 10.2 Deux chemins pour lever le blocage, sans ordre de préférence imposé

**A. Attendre qu'un wheel `pydantic-core` Android officiel soit publié.** Dépend entièrement de l'équipe Pydantic (ou de la communauté PyO3/maturin) — aucun calendrier connu, aucune garantie. Coût d'attente : nul en ingénierie, mais pas d'échéance à donner à qui que ce soit.

**B. Compiler soi-même un wheel `pydantic-core` pour Android.** Rust supporte officiellement la compilation croisée vers les cibles Android (`aarch64-linux-android`, `x86_64-linux-android`) via le NDK. En théorie :
1. Installer le toolchain Rust + Android NDK + [`cargo-ndk`](https://github.com/bbqsrc/cargo-ndk).
2. Cloner les sources de `pydantic-core` (même version que celle utilisée sur les autres plateformes, pour rester synchronisé).
3. Compiler avec `maturin build --target aarch64-linux-android` (et `x86_64-linux-android` pour l'émulateur/tests), en visant l'ABI CPython exacte utilisée par Chaquopy (3.13 au moment de l'écriture — cf. Lot 0).
4. Le wheel produit peut être utilisé **directement, sans publication** : Chaquopy accepte un fichier `.whl` local relatif au projet dans `chaquopy.pip.install("chemin/vers/le.whl")` (confirmé dans la documentation officielle consultée au Lot 0).
- **Risque principal, non levé par la théorie ci-dessus** : `pydantic-core` n'étant pas un simple binding C mais un projet PyO3 avec des dépendances Rust propres (dont potentiellement des bibliothèques nécessitant elles-mêmes un portage Android), la compilation croisée peut buter sur des problèmes non documentés — le fait qu'aucun wheel Android n'existe ni sur PyPI ni sur l'index communautaire de Chaquopy est un indice (faible, pas une preuve) que ce n'est pas trivial, sans quoi quelqu'un l'aurait probablement déjà fait et publié.
- **Effort réaliste, à la louche, pas un engagement** : de quelques jours à quelques semaines pour quelqu'un découvrant PyO3/la compilation croisée Android, avec un risque réel d'échec en bout de course — ce n'est pas un simple `cargo build --target ...` qui marche du premier coup en pratique pour un projet de cette taille.

### 10.3 Ce qu'il faudrait changer dans ce dépôt le jour où un wheel fonctionne — bonne nouvelle : presque rien

Tous les correctifs de compatibilité v1 (§3.1, Découvertes des Lots 0 et 2 dans [`docs/plan-implementation-android.md`](plan-implementation-android.md)) ont été écrits avec le même principe : **`try: <syntaxe v2> except ImportError: <repli v1>`** (ou `getattr(obj, "nom_v2", None) or obj.nom_v1`), jamais une branche figée sur une seule version. Conséquence directe : le jour où `pydantic-core` a un wheel Android fonctionnel, il suffit de :
1. Mettre à jour `android/app/build.gradle.kts` : remplacer les pins `pydantic==1.10.26`/`fastapi==0.99.1` par les mêmes versions que les autres plateformes, et ajouter l'installation du wheel `pydantic-core` compilé (§10.2).
2. **Aucun changement requis dans `backend/app/`** : chaque `try/except ImportError` empruntera automatiquement la branche v2, puisque l'import v2 réussira désormais sur Android aussi.
3. Par propreté seulement (pas par nécessité fonctionnelle) : les clés `orm_mode = True` redondantes et le module [`backend/app/utils/_pydantic_compat.py`](../backend/app/utils/_pydantic_compat.py) pourraient être retirés — mais les laisser ne casse rien, ils deviennent simplement inertes.

Ce choix de conception (tout en repli conditionnel, jamais en divergence de fichiers) est ce qui rend ce compromis réversible à faible coût — la vraie dépense, si elle a lieu, sera dans la compilation du wheel (§10.2), pas dans la réconciliation du code applicatif.

### 10.4 Comment vérifier périodiquement si la situation a changé

Sans mettre en place une surveillance automatisée (hors périmètre de ce rapport), un futur agent ou mainteneur peut vérifier manuellement :
```bash
# Le paquet a-t-il maintenant une distribution pour Android ?
pip index versions pydantic-core --index-url https://pypi.org/simple
# Chercher un tag de plateforme contenant "android" dans les noms de wheels listés.
```
et consulter le [changelog Chaquopy](https://chaquo.com/chaquopy/doc/current/changelog.html) pour une éventuelle annonce d'un dépôt de wheels élargi incluant `pydantic-core`.
