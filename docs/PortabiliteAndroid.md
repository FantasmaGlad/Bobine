# Cahier des charges & Faisabilité — Portabilité Android (Bobine sur Tablette)

> Document prospectif pour le portage futur de Bobine sur l'écosystème Android (tablettes dédiées avec sortie HDMI).

---

## 1. Vision & Cas d'Usage (Le "Tout-en-un" Studio)

Dans l'architecture historique, Bobine nécessite un mini PC x86-64 (ex. Dell Wyse 5070 ou mini PC de salon) connecté en HDMI à l'écran de la salle, et l'utilisateur accède à l'administration via son smartphone ou un PC distant sur le réseau local.

**La vision Android** :
Transformer une tablette Android moderne (ex. Xiaomi Pad 6, Pad 7, Galaxy Tab S8/S9) en une station autonome complète via un **seul fichier APK**, connectée à un **dock USB-C avec alimentation Power Delivery et sortie HDMI** :
1. **Écran tactile de la tablette (fixé au mur du studio)** : Affiche en continu le panneau d'administration, la télécommande tactile et le planning pour les coachs et les adhérents.
2. **Écran TV / Vidéoprojecteur (via le câble HDMI du dock)** : Affiche le flux plein écran `/cinema` ou `/kiosk` en 1080p / 4K 60 fps avec accélération matérielle VPU native.
3. **Serveur Backend autonome** : La tablette héberge elle-même le serveur FastAPI, SQLite et publie `bobine.local` sur le réseau Wi-Fi de la salle.

---

## 2. Architecture 100% Autonome (Sans Termux)

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
│  │   │  (Keep-alive 24/7)  │   │   & Presentation     │  │  │
│  │   └──────────┬──────────┘   └──────────┬───────────┘  │  │
│  └──────────────┼─────────────────────────┼──────────────┘  │
│                 │                         │                 │
│  ┌──────────────▼──────────┐   ┌──────────▼──────────────┐  │
│  │ Chaquopy (CPython 3.11) │   │   Deux Vues Découplées  │  │
│  │                         │   │                         │  │
│  │ • FastAPI + Uvicorn     │   │ 1. Tablette : Admin UI  │  │
│  │ • SQLite (database.db)  │   │    (WebView tactile)    │  │
│  │ • APScheduler, zeroconf │   │ 2. TV HDMI : Kiosque    │  │
│  │ • ffmpeg-kit-android    │   │    (Presentation 4K)    │  │
│  └─────────────────────────┘   └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Cœur Backend : Chaquopy (CPython embarqué)
- **Chaquopy** est le SDK standard industriel pour exécuter Python au sein d'une application Android native.
- L'interpréteur CPython et les paquets PyPI purs (`fastapi`, `uvicorn`, `apscheduler`, `pydantic-settings`, `starlette`) ainsi que les bibliothèques C compilées pour ARM64 (`sqlite3`, `pydantic-core`) sont intégrés directement dans l'APK.
- Au lancement de l'application, l'activité Android démarre un `ForegroundService` qui instancie le thread Python et exécute :
  ```python
  uvicorn.run("app.main:app", host="0.0.0.0", port=8000, workers=1)
  ```
- Le backend démarre en moins de 2 secondes au lancement de l'application.

### 2.2 Gestion Double Écran : `android.app.Presentation`
Android gère nativement le multi-affichage via l'API [`DisplayManager`](https://developer.android.com/reference/android/hardware/display/DisplayManager) :
- Dès que le câble HDMI est branché sur le dock USB-C, Android émet un évènement `DisplayListener.onDisplayAdded(displayId)`.
- L'application instancie une classe héritant de `android.app.Presentation(context, display)` :
  - Cette vue s'affiche **exclusivement sur la sortie HDMI (la TV)** et charge `http://localhost:8000/kiosk` (ou `/cinema`).
  - L'écran principal de la tablette continue d'afficher l'interface d'accueil ou d'administration (`http://localhost:8000`).
- Si aucun écran externe n'est détecté, la tablette peut afficher au choix le kiosque ou l'admin avec un bouton de bascule rapide.

### 2.3 Décodage Vidéo Matériel & FFmpeg
- **Lecture Vidéo** : Le rendu du `<video>` HTML5 dans le `WebView` Android exploite automatiquement les décodeurs matériels MediaCodec (VPU Qualcomm Adreno / MediaTek Mali) pour les formats H.264, H.265 (HEVC) et AV1 en 4K 60 fps, sans faire chauffer la tablette et avec une consommation inférieure à 5 Watts.
- **Utilitaires FFmpeg** (analyse des durées des cours, extraction de vignettes d'import) : Intégration de la bibliothèque native `ffmpeg-kit-android` (binaires C précompilés sous forme de `.aar` Android) accessible depuis Python via `ctypes` ou liaison JNI.

---

## 3. Réseau, Découverte & Alimentation

### 3.1 Port d'écoute & Découverte mDNS (`bobine.local`)
- **Port 8000** : Android autorise les sockets TCP non privilégiés (> 1024) sans root. L'API et les WebSockets écoutent sur le port 8000.
- **Résolution mDNS** : Pour que les smartphones du personnel puissent se connecter via `http://bobine.local:8000`, l'application acquiert un `MulticastLock` :
  ```kotlin
  val wifiManager = context.getSystemService(Context.WIFI_SERVICE) as WifiManager
  val multicastLock = wifiManager.createMulticastLock("bobine_mdns_lock")
  multicastLock.setReferenceCounted(true)
  multicastLock.acquire()
  ```
  Le module Python `zeroconf` existant de Bobine peut alors émettre et recevoir librement les annonces réseau.

### 3.2 Stockage des Médias & Vidéos
- Les vidéos et cours sont stockés dans le stockage applicatif étendu :
  `context.getExternalFilesDir(null)` (chemin type `/sdcard/Android/data/com.bobine.app/files/data/videos/`).
- Cet emplacement offre un espace de stockage gigaoctet sans demander de permissions Android intrusives.
- Support du stockage externe USB OTG : les gérants peuvent insérer une clé USB sur un port du dock USB-C pour importer des cours directement dans l'application.

### 3.3 Fonctionnement Continu 24h/24 & Mode Kiosque
- **Survie du processus** :
  - Déclaration d'un `ForegroundService` avec une notification persistante (*"Bobine diffuse en arrière-plan"*).
  - Demande de désactivation des optimisations de batterie (`ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`).
- **Mode Kiosque (Lock Task Mode / Device Owner)** :
  - L'application peut être configurée comme gestionnaire de l'appareil (*Device Owner* via commande `adb shell dpm set-device-owner com.bobine.app/.DeviceAdminReceiver`), empêchant quiconque de quitter l'application, de voir les notifications système Android ou d'accéder aux réglages de la tablette.
- **Protection de la batterie** :
  - Sur les tablettes Xiaomi (HyperOS) et Samsung (One UI), activer la fonction native "Protection de la batterie" qui plafonne la charge à 80% pour préserver la chimie de la batterie lors d'un branchement 24/7 sur secteur.

---

## 4. Prérequis Matériels Stricts (Checklist Achat)

Toutes les tablettes Android ne sont pas compatibles. Le critère bloquant est la norme du port USB-C :

| Composant | Exigence minimale | Exemple de modèles recommandés | Modèles INCOMPATIBLES |
|---|---|---|---|
| **Port USB-C** | **USB 3.2 Gen 1 avec DisplayPort Alt Mode** | Xiaomi Pad 6, Xiaomi Pad 6 Pro, Xiaomi Pad 7, Samsung Galaxy Tab S7 / S8 / S9 | Xiaomi Redmi Pad (USB 2.0), Xiaomi Pad 5 standard (USB 2.0), Lenovo Tab M10 (USB 2.0) |
| **SoC / Processeur** | Snapdragon 870 ou supérieur (décodage 4K matériel) | Qualcomm Snapdragon 870, 8+ Gen 1, 8s Gen 3 | SoCs d'entrée de gamme sans décodage HEVC 60fps fluide |
| **Stockage** | 128 Go ou 256 Go UFS | 128 Go minimum pour stocker ~100 cours vidéo HD | 32 Go ou 64 Go eMMC |
| **Dock USB-C** | Hub avec HDMI 4K@60Hz + USB-C PD (Power Delivery ≥ 45W) + Ports USB-A | Docks Anker, Ugreen ou Baseus avec entrée secteur PD 65W | Adaptateurs simples sans injection de courant |

---

## 5. Plan de Développement Estimatif (Feuille de Route)

1. **Jalon 1 : PoC Chaquopy & Serveur FastAPI** (2 jours)
   - Création du projet Android Studio (Kotlin, MinSDK 26).
   - Intégration du plugin Gradle Chaquopy et validation du démarrage d'`app.main:app` sur le port 8000.
   - Validation de l'accès à `http://127.0.0.1:8000/api/health`.

2. **Jalon 2 : Intégration de `Presentation` & Double Affichage** (2 jours)
   - Écoute des connexions d'écrans externes via `DisplayManager`.
   - Création de la vue `Presentation` contenant un `WebView` plein écran configuré pour le flux `/kiosk`.
   - Affichage de la télécommande / admin sur le `WebView` principal de la tablette.

3. **Jalon 3 : Résilience Réseau & Mode Kiosque** (2 jours)
   - Implémentation du `ForegroundService`, du `WakeLock` et du `MulticastLock`.
   - Validation de `bobine.local` depuis un iPhone ou un PC connecté au même point d'accès Wi-Fi.
   - Configuration du mode plein écran immersif (*Sticky Immersive Mode*).

4. **Jalon 4 : Packaging & Pipeline CI** (1 jour)
   - Script Gradle pour exporter le frontend statique Next.js (`npm run build`) vers `app/src/main/assets/out/` avant la compilation de l'APK.
   - Job GitHub Actions produisant automatiquement `Bobine.apk` lors des releases.
