# Audit Android — lenteur réseau, sortie câblée intermittente, saccades vidéo, chemins de stockage (2026-09-11)

Document de diagnostic et plan d'implémentation. Il fait suite à [`diagnostic-freeze-android-2026-09-10.md`](diagnostic-freeze-android-2026-09-10.md) et complète [`plan-implementation-android.md`](plan-implementation-android.md) (Lot 15, ci-dessous). Les règles de session du diagnostic précédent restent en vigueur (aucune mention IA dans les commits ni la documentation, pas d'emoji, aucune interaction tactile automatisée sur la tablette sans accord explicite).

Périmètre : version Android uniquement (Xiaomi Pad 8, `192.168.1.60:8000`, APK Chaquopy). Les autres profils (`.deb`, headless `install.sh`, `.exe`, `.dmg`) n'exhibent pas ces symptômes d'après l'utilisateur ; ce document explique pourquoi les mêmes fichiers source se comportent différemment sur la tablette.

**Statut (2026-09-11) : Lot 15 exécuté ET validé en conditions réelles sur la tablette pilote physique** (Xiaomi Pad 8), sur confirmation explicite de l'utilisateur — étapes 15.1 à 15.4 et 15.6 implémentées, plus un correctif serveur critique (15.4bis) trouvé PENDANT ce déploiement réel : `RevalidateStaticFiles` (`backend/app/main.py`) servait par erreur des pages HTML périmées après mise à jour (ETag non basé sur le contenu réel + repli `If-Modified-Since` structurellement cassé par le build reproductible), expliquant directement le rapport « `/grid` n'affiche aucune vidéo ». Corrigé, reconstruit, redéployé sur le même appareil et reconfirmé : `/grid`/`/cinema` reçoivent 200 après mise à jour, zéro 404, la bibliothèque réelle (vidéo + miniature) s'affiche. Migration de stockage confirmée sur DONNÉES RÉELLES de production (base SQLite existante migrée vers le stockage interne, réglages utilisateur préservés, original externe jamais touché). Étape 15.5 délibérément différée. Mission secondaire (installateur headless) traitée. Détail complet dans la section « Lot 15 » de [`plan-implementation-android.md`](plan-implementation-android.md#16octies-lot-15--performance-stabilité-réseau-cohérence-bibliothèque-et-thème-charbon-sombre-2026-09-11).

---

## 1. Symptômes rapportés

| # | Symptôme | Canal / surface |
|---|---|---|
| S1 | La sortie câblée ne répond pas à tous les coups à une commande de l'interface admin | `BobinePresentation` (WebView HDMI, `127.0.0.1/cinema`), commandes `cinema_command` |
| S2 | Lenteur et non-réponse dès que plusieurs instances sont connectées sur `192.168.1.60:8000`, y compris en local `127.0.0.1`, sauf rechargements forcés répétés | Backend embarqué (uvicorn + h11 + websockets purs Python) |
| S3 | `/kiosk` câblé joue la vidéo avec énormément de saccades et de gels | `BobinePresentation` basculée sur `/kiosk` par `display_output cable=kiosk` |
| S4 | `/kiosk` réseau démarre puis gèle rapidement ; la tête de lecture admin ne le contrôle pas | Kiosk réseau (Chrome sur la tablette ou autre appareil du LAN), canal `network` |
| S5 | Les fichiers disparaissent parfois de l'affichage puis réapparaissent ; un titre modifié ne se met pas à jour instantanément | `/library`, `/grid`, `/cinema` (liste `GET /api/videos`) |

Les cinq symptômes ne sont pas cinq bugs indépendants. Trois causes structurelles, toutes amplifiées par Android, les expliquent ensemble ; deux causes secondaires expliquent le reste.

---

## 2. Causes racines identifiées (par ordre de probabilité et d'impact)

### C1. Blocage de la boucle d'évènements par des appels SQLite synchrones, sur un stockage FUSE lent

**Faits établis dans le code** (identiques sur toutes les plateformes) :

- Le backend est mono-processus, une seule boucle asyncio (`bobine_bootstrap.py` : `uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)`), sans `uvloop` ni `httptools` (indisponibles sous Android, cf. Lot 0) : parseur HTTP `h11` et bibliothèque `websockets` en Python pur.
- Plusieurs handlers **`async def`** exécutent des requêtes SQLAlchemy **synchrones directement sur la boucle** :
  - `backend/app/main.py` : les cinq endpoints `stream_*` (`/api/videos/{id}/stream`, fonds, audio, radio) font `db.query(...)` puis `file_path.exists()`/`stat()` avant de répondre. Chromium émet des dizaines de requêtes Range par lecture (une par fenêtre de tampon) : chacune bloque la boucle le temps d'une requête SQLite et d'un `stat` sur le système de fichiers.
  - `backend/app/routers/playback.py` : `playback_ws` reçoit `db: Session = Depends(get_db)` et `_handle_command` fait `db.query(Video/Background/AudioCourse/Playlist)` et `get_display_output_value(db, ...)` (verrou cinéma) **sur la boucle**, pour chaque commande `load`, `load_playlist`, `load_audio_course`, `load_background`.
  - `routers/settings.py` (`set_display_output`, `update_settings`, `upload_logo`, `delete_logo`), `routers/schedule.py` (create/update/delete), `routers/videos.py::upload_video_thumbnail`, `routers/updates.py`, `main.py::health` (`SessionLocal()` + `psutil.process_iter` sur toute la table des processus, très lent sous SELinux Android).
- `PRAGMA busy_timeout=30000` (`database.py`) : un `db.query` synchrone qui rencontre un verrou d'écriture **bloque la boucle jusqu'à 30 s**. Pendant ce temps : aucune requête HTTP servie, aucun message WebSocket relayé, aucun `position_tick`, aucun ping/pong.
- Les écritures concurrentes existent en permanence sur la tablette : `log_activity` (commit à chaque commande), `import_jobs` (progression d'encodage), `report_position` non, mais le watcher polling (`_polling_observer.py`, toutes les 2 s) et les handlers synchrones dans le threadpool anyio (40 threads) ouvrent leurs propres transactions.

**Pourquoi Android seulement** :

- `DATA_ROOT` = `context.getExternalFilesDir(null)` = `/storage/emulated/0/Android/data/com.bobine.app/files` (Lot 9). Sur Android 11+, ce chemin est servi par **FUSE** (émulation du stockage partagé), pas par ext4/f2fs directement. Chaque `open`/`stat`/`read` passe par le démon FUSE (contexte utilisateur, changement de contexte par appel) ; les performances sont plusieurs fois inférieures au stockage interne, et Google documente que SQLite n'est **pas supporté sur le stockage externe** (mmap de `-shm` en mode WAL, verrous POSIX partiellement émulés). Résultat : `database.db`, `-wal` et `-shm` vivent sur FUSE, chaque requête est lente, chaque verrou plus long, et le mode WAL peut retomber silencieusement en `delete` (à vérifier, §4).
- Les médias sont aussi sur FUSE : `aiofiles` lit par blocs de 128 Ko via un thread, soit un aller-retour FUSE par bloc. Pour un flux 4K 60 fps à 28 Mbit/s (politique de conservation native, `_get_target_bitrate`), c'est environ 27 blocs par seconde par lecteur, en concurrence GIL avec la boucle et les threads d'import.
- Sur le Wyse/`.deb`/`.exe`, la base et les médias sont sur un disque local natif avec un CPU x86 : les mêmes appels synchrones durent quelques centaines de microsecondes et ne se voient pas.

**Symptômes expliqués** : S2 (tout ralentit dès que plusieurs clients tirent des flux Range et des commandes en même temps ; F5 répété « marche » parce qu'il finit par tomber entre deux blocages), S1 et S4 en partie (une commande admin émise pendant un blocage de la boucle est traitée en retard ou son WebSocket est fermé par le ping/pong, cf. C2), S5 (un `PUT /api/videos/{id}` ou un `GET /api/videos` qui dépasse le délai côté client affiche une erreur ou une liste vide, puis la liste revient au fetch suivant).

### C2. Diffusion WebSocket séquentielle sans délai de garde, et keepalive trop strict pour des WebViews Android

- `ws_manager.broadcast()` fait `await connection.send_json(message)` **client par client, en série**, sans `asyncio.wait_for`. Un client dont le tampon TCP est plein (onglet Chrome en arrière-plan sur la tablette, WebView non visible, Wi-Fi qui rame) **bloque la diffusion pour tous les autres**. `position_tick` est émis toutes les 250 ms par canal actif : à la moindre latence, les ticks s'empilent derrière un client lent.
- Chaque page admin ouvre **deux** WebSockets (`AppSettingsContext.tsx` ouvre le sien sur toutes les pages, plus le hook `usePlaybackSocket` de la page). Sur la tablette elle-même : `/grid` (2), `BobinePresentation` (2), chaque onglet Chrome admin (2), plus les kiosks/téléphones du LAN. À 10 clients, un `broadcast` = 10 envois en série toutes les 250 ms.
- `PING_INTERVAL_SECONDS=30` / `PONG_TIMEOUT_SECONDS=20` : Chromium/WebView gèle les minuteurs JS des pages non visibles (1 réveil par seconde, puis 1 par minute après cinq minutes en « intensive throttling »). La `MainActivity` (`/grid`) passe en arrière-plan dès que l'utilisateur ouvre Chrome pour l'admin ; ses `pong` arrivent en retard, le serveur ferme la connexion, le client reconnecte (backoff 1 s à 30 s) et rejoue ses commandes de moins de 5 s. Les commandes émises pendant cette fenêtre sont perdues ou doublées.
- `BobinePresentation` est créée par le `ForegroundService`, sans `Activity` visible : sa WebView est bien affichée sur l'écran HDMI, mais l'app entière est en importance « service au premier plan », pas « top ». HyperOS applique des restrictions CPU/réseau à ce niveau. Ni `setRendererPriorityPolicy(RENDERER_PRIORITY_IMPORTANT, false)` ni `onResume()` explicite ne sont appelés sur cette WebView.

**Symptômes expliqués** : S1 (une commande `cinema_command` sur trois est perdue pendant une reconnexion ou retardée derrière un client lent), S4 (le kiosk réseau rate un `seek`, ou reçoit un `position_tick` périmé et se recale en arrière), et la charge CPU de C1 est aggravée par les reconnexions en rafale (déjà observée au Lot 9 : une cinquantaine de reconnexions en 2 s au démarrage de `/cinema`).

**Bug réel trouvé APRÈS le premier correctif de C2 (parallélisation de `broadcast()`), en testant le tableau de bord admin en conditions réelles sur Wi-Fi — réf. retour utilisateur "la connexion entre le dashboard admin et le réseau reste incertain, avec des freeze, des lags, des répétitions".** Diagnostiqué par un client WebSocket de test se connectant depuis la machine de développement vers le vrai backend de la tablette (pas un test local) : `position_tick` s'arrêtait **net et silencieusement** après quelques secondes de lecture active, sans la moindre reconnexion détectée côté client, alors que le même scénario tournait 40 secondes sans le moindre accroc contre le serveur de développement en local. Cause : `broadcast()` (la version parallélisée de ce lot) retire un client du délai de garde de `active_connections` via `self.disconnect(connection)` **sans jamais appeler `connection.close()`** — le client, lui, ne reçoit ni frame de fermeture ni erreur, son objet WebSocket reste `OPEN` indéfiniment de son propre point de vue, alors que le serveur a cessé de lui diffuser quoi que ce soit. Sur une vraie connexion Wi-Fi (latence/gigue réelles, absentes de tout test en local), un seul envoi dépassant `BROADCAST_SEND_TIMEOUT_SECONDS` (1.0s à l'origine, jugé trop strict après coup) suffisait à faire taire silencieusement le dashboard pour de bon — jusqu'au keepalive serveur (jusqu'à 90s). **C'est très probablement LA cause directe du rapport "freeze, lags, répétitions" du dashboard réseau.** Corrigé en deux temps : `connection.close()` appelé avant `disconnect()` (même ordre que le timeout de `_ping_loop`, déjà correct depuis l'origine — la parallélisation de C2 avait simplement oublié ce détail), et le délai porté à 3.0s pour éviter de classifier à tort un envoi Wi-Fi simplement lent comme mort. Un chien de garde de silence a aussi été ajouté côté client (`usePlaybackSocket.ts`) : indépendamment de la cause, un tableau de bord au premier plan qui ne reçoit plus RIEN pendant 5s (en lecture active) ou 35s (au repos) force sa propre reconnexion plutôt que d'attendre le keepalive serveur — filet de sécurité générique contre tout silence non détecté par ailleurs. Test de régression dédié : `backend/tests/test_ws_manager_threadsafe.py::test_broadcast_actually_closes_a_client_that_times_out`.

### C3. Racine de données non fiable au démarrage (stockage externe absent ou retardé)

- `BobineForegroundService.kt` passe `getExternalFilesDir(null)?.absolutePath`, **nullable**, à `start_server_once`. `bobine_bootstrap.py` ne pose `BOBINE_ANDROID_DATA_DIR` que si la valeur est non nulle ; sinon `config.py::_data_root()` retombe **silencieusement** sur `ROOT_DIR` = `AssetFinder/app/` (dossier interne redéployé par Chaquopy à chaque mise à jour, cf. Lot 9).
- `getExternalFilesDir` renvoie `null` tant que le stockage externe n'est pas monté (démarrage à froid avec `START_STICKY`, redémarrage du service après un kill mémoire pendant un boot, passage en mode transfert USB sur certains OEM). Le service reste alors sur une **seconde base vide** jusqu'au prochain redémarrage du processus : la bibliothèque paraît vide, les miniatures 404, puis tout « réapparaît » après relance. Une modification faite pendant cette fenêtre est écrite dans la mauvaise base et perdue à la mise à jour suivante.
- `DATA_ROOT` est calculé une seule fois au niveau module : aucune détection ultérieure du montage n'est possible sans redémarrer Python.

**Symptômes expliqués** : S5 (disparition/réapparition), et un risque de perte de données réel.

### C4. WebViews sans cache HTTP (`LOAD_NO_CACHE`) et double WebView sur le même backend

- `MainActivity.kt` et `BobinePresentation.kt` forcent `WebSettings.LOAD_NO_CACHE`. Ce réglage date d'avant le correctif serveur `Cache-Control: no-cache` + ETag (`RevalidateStaticFiles`, `main.py`). Il est désormais redondant et coûteux : chaque chargement de page re-télécharge intégralement les bundles JS/CSS (plusieurs Mo) à travers h11 pur Python et FUSE, au lieu d'un 304. Chaque reconnexion « boot_id changé » ou « force_reload » repasse par là.
- Effet direct sur S2 : un rechargement de `/grid` ou `/cinema` sature la boucle pendant plusieurs secondes.

**Correction critique découverte en déployant réellement sur la tablette pilote (pas en relecture de code) : `RevalidateStaticFiles` était structurellement cassée, sur TOUTES les plateformes, pas seulement Android.** Deux bugs empilés :
1. L'ETag par défaut de Starlette (`FileResponse.set_stat_headers`) est `md5(mtime + "-" + taille)`, PAS un hachage du contenu réel — contrairement à ce qu'affirmait le commentaire de cette classe. Le mtime étant normalisé à une date fixe par le build reproductible, deux versions différentes d'un fichier de même taille (fréquent pour un petit shell HTML) obtiennent le même ETag.
2. Même une fois l'ETag corrigé (recalculé depuis le contenu réel), `StaticFiles.is_not_modified()` retombe sur une comparaison `If-Modified-Since` vs `Last-Modified` quand le client n'envoie PAS `If-None-Match` — et `Last-Modified` reste, lui, calculé depuis ce même mtime figé. N'importe quelle date envoyée par le client satisfait alors la condition « non modifié ». **Constaté empiriquement : le cache HTTP natif de la WebView Android n'envoie pas systématiquement `If-None-Match`**, et retombait donc systématiquement sur ce second chemin cassé.
Ensemble, ces deux bugs expliquent directement le rapport utilisateur « `/grid` n'affiche aucune vidéo » : après une mise à jour de l'app, `GET /grid/` recevait un 304 à tort, servant une page HTML mise en cache référençant des bundles JS d'une build antérieure — 404 en cascade sur ces bundles, page cassée silencieusement. Reproduit et confirmé en conditions réelles sur la tablette pilote (`curl -H "If-Modified-Since: <date récente>"` → 304 malgré un contenu réellement différent), corrigé, puis reconfirmé sur le même appareil après correction (0 404, `/grid`/`/cinema` reçoivent 200 après une mise à jour). Voir §5 étape 15.4bis et les Découvertes du Lot 15 pour le détail complet.

### C5. Rendu vidéo 4K 60 fps dans une WebView (pas un SurfaceView)

- La politique d'import conserve la résolution et la cadence natives (28 Mbit/s en 4K UHD). Dans une **WebView**, les images vidéo décodées par MediaCodec ne passent pas par une surface overlay (SurfaceView) mais par le compositeur Chromium (texture GPU par image, composition dans l'arbre de rendu, puis composition SurfaceFlinger vers l'écran HDMI 2560x1600). À 60 images/s en 4K, c'est le chemin le plus coûteux possible sur une tablette ; Chrome Android (application complète) sait utiliser un overlay, la WebView non.
- Combiné à C1 (lecture FUSE par blocs de 128 Ko, boucle bloquée par les requêtes Range) et C2 (app en importance « service »), l'image saccade et le watchdog `requestVideoFrameCallback` (Lot « freeze au seek ») déclenche des micro-seeks de rattrapage toutes les 2,5 s, ce qui **ajoute** des gels visibles (pause, seek, `seeked`, play) au lieu de les corriger.

**Symptômes expliqués** : S3 (saccades câblé), une partie de S4.

### Écarts secondaires constatés en passant (à corriger dans le même lot, faible coût)

- `main.py::health` énumère tous les processus via `psutil.process_iter` sur la boucle d'évènements ; sous Android chaque `/proc/<pid>` refusé lève une exception capturée, plusieurs centaines de fois. Inutile sur ce profil (pas de kiosque Chromium à détecter).
- `RetryingSession.commit` fait `time.sleep` : dans un handler `async def`, c'est un blocage de boucle supplémentaire (jusqu'à 0,2 + 0,4 + 0,8 s).
- `_position_broadcast_loop` émet même si aucun client n'a changé depuis le dernier tick ; pas de coalescence.
- `bobine_bootstrap.py` ne passe ni `timeout_keep_alive` ni `ws_ping_interval=None` à uvicorn : le keepalive HTTP par défaut de 5 s force Chromium à rouvrir une connexion TCP entre deux requêtes Range espacées, et uvicorn envoie ses propres pings WebSocket (20 s) en plus de ceux de `ws_manager`.
- `WebView.setWebContentsDebuggingEnabled(true)` est actif en release (commentaire « debug uniquement » non respecté) : coût faible, mais surface d'attaque locale inutile en production.

---

## 3. Ce qui a déjà été corrigé et ne doit pas être refait

- Freeze au seek (pause/`seeked`, garde `seeking`, période de grâce, watchdog rVFC) : Lot « diagnostic 2026-09-10 ». Le plan ci-dessous **désarme** le watchdog pendant les périodes de saturation plutôt que de le retirer.
- Imports atomiques `temp_norm_*`, plages suffixées `bytes=-N`, `Content-Range` retiré des 200.
- Cache HTTP côté serveur (`Cache-Control: no-cache` + ETag) : c'est précisément ce qui rend C4 corrigeable sans risque de servir une vieille version.
- Vitrine `/cinema` réseau, `/grid` tactile, `cinema_command` `launch`.

---

## 4. Mesures à faire AVANT d'implémenter (une demi-journée, lecture seule sur la tablette)

Chaque mesure confirme ou infirme une cause ; toutes se font par `adb shell` et l'API HTTP, sans toucher à l'écran de la tablette.

| Cause | Mesure | Résultat attendu si la cause est confirmée |
|---|---|---|
| C1 (FUSE) | `adb shell "run-as com.bobine.app cat /proc/mounts" \| grep -E 'emulated\|fuse'` puis `adb shell "time dd if=/storage/emulated/0/Android/data/com.bobine.app/files/data/videos/<un fichier> of=/dev/null bs=128k count=800"` et la même commande avec un fichier copié sous `/data/data/com.bobine.app/files/` | Débit FUSE nettement inférieur (facteur 2 à 5) au stockage interne |
| C1 (WAL) | Ajouter temporairement un log du retour de `PRAGMA journal_mode=WAL` dans `_set_sqlite_pragma`, ou exécuter `adb shell run-as com.bobine.app sqlite3 .../database.db 'PRAGMA journal_mode;'` | Retour `delete` au lieu de `wal`, ou erreurs « disk I/O error » dans `data/logs/technical.log` |
| C1 (boucle bloquée) | Depuis le PC : boucle `curl -o /dev/null -s -w '%{time_total}\n' http://192.168.1.60:8000/api/time` toutes les 200 ms pendant qu'un kiosk réseau lit une vidéo et qu'un import tourne | Pics de plusieurs secondes sur un endpoint qui ne fait rien d'autre que `time.time()` |
| C2 (keepalive) | `adb logcat -s WebViewConsole BobinePresentationConsole python.stderr` en ouvrant l'admin dans Chrome sur la tablette | « Client WebSocket sans pong dans le délai » côté Python et reconnexions côté WebView toutes les 50 s environ |
| C2 (priorité process) | `adb shell dumpsys activity processes \| grep -A3 bobine` avec Chrome au premier plan | `com.bobine.app` et `:sandboxed_process0` en importance `FGS`/`PERC`, pas `TOP` |
| C3 | `adb logcat -s python.stderr \| grep 'Watcher : Initialisation'` juste après un redémarrage à froid de la tablette | Chemin `AssetFinder/app/data/...` au lieu de `/storage/emulated/0/...` sur au moins un démarrage |
| C5 | `adb shell dumpsys SurfaceFlinger --latency` et `adb shell top -n 3` pendant une lecture 4K 60 sur HDMI | `sandboxed_process` et `surfaceflinger` proches de 100 % d'un cœur, frame drops dans la latence |

Les résultats sont à consigner dans la section « Découvertes » du Lot 15 (`plan-implementation-android.md`) avant de commencer l'implémentation.

---

## 5. Plan d'implémentation — Lot 15

Ordre imposé par les dépendances et le rapport bénéfice/risque. Chaque étape est livrable et testable seule ; aucune ne casse les autres profils (les changements backend sont soit neutres, soit conditionnés au profil `android` via `deployment.get_deployment_profile()` ou `hasattr(sys, "getandroidapilevel")`).

### Étape 15.1 — Base SQLite et petits fichiers sur le stockage interne, médias sur l'externe (C1, C3)

Fichiers : `android/app/src/main/java/com/bobine/app/BobineForegroundService.kt`, `android/app/src/main/python/bobine_bootstrap.py`, `backend/app/config.py`, `scripts/migrate_unify_data_dirs.py` (réutilisé pour la migration), `docs/plan-implementation-android.md` (Lot 9).

- [ ] Kotlin : transmettre **deux** racines à Python : `filesDir` (interne, ext4/f2fs natif, jamais FUSE) et `getExternalFilesDir(null)` (médias). Si l'externe est `null`, **ne pas démarrer le serveur** : journaliser, afficher une notification « stockage indisponible », réessayer toutes les 5 s (`Handler.postDelayed`) jusqu'au montage. Plus jamais de repli silencieux sur `AssetFinder/app/`.
- [ ] Python (`config.py`, branche `Android`) : `database_url`, `thumbnails_dir`, `logs_dir`, `branding_dir`, `radio_covers_dir` sous la racine interne ; `media_dir`, `backgrounds_dir`, `audio_dir`, `radio_dir`, `radio_announcements_dir`, dossiers surveillés et `tmp/` sous l'externe. Variables `BOBINE_ANDROID_INTERNAL_DIR` et `BOBINE_ANDROID_DATA_DIR`.
- [ ] Migration au premier démarrage de la nouvelle version : si `<externe>/data/database.db` existe et pas `<interne>/data/database.db`, copier base + `-wal` + `-shm` (après `PRAGMA wal_checkpoint(TRUNCATE)` via `sqlite3` stdlib), miniatures et logs ; ne jamais supprimer l'original avant vérification `PRAGMA integrity_check` sur la copie. Les chemins absolus de `videos.file_path`, `thumbnail_path` etc. stockés en base sont réécrits par préfixe (même logique que `migrate_unify_data_dirs.py`).
- [ ] `database.py` : journaliser la valeur réellement retournée par `PRAGMA journal_mode` au premier `connect` (une ligne INFO), pour ne plus jamais deviner.
- [ ] Vérifier `/api/settings/storage` (`_dir_size`) : deux racines à agréger sur ce profil.

Critère de sortie : après redémarrage à froid de la tablette avec écran branché, `technical.log` montre la base sous `/data/data/com.bobine.app/files/...`, `journal_mode=wal`, et `GET /api/videos` répond en moins de 100 ms (mesure `curl -w`).

### Étape 15.2 — Sortir toute I/O bloquante de la boucle d'évènements (C1)

Fichiers : `backend/app/main.py`, `backend/app/routers/playback.py`, `backend/app/routers/settings.py`, `backend/app/routers/schedule.py`, `backend/app/routers/videos.py`, `backend/app/database.py`.

- [ ] `stream_*` (`main.py`) : résoudre le chemin et la taille dans `await run_in_threadpool(...)` (ou passer les endpoints en `def` synchrones et ne garder qu'un `StreamingResponse` avec `aiofiles`). Envisager un cache mémoire `{id: (path, size, mtime)}` invalidé par les routers d'écriture, pour ne plus toucher SQLite à chaque requête Range.
- [ ] `stream_*` : passer la taille de bloc de 128 Ko à 1 Mo sur Android (moins d'allers-retours FUSE/thread) ; laisser 128 Ko ailleurs.
- [ ] `_handle_command` : toutes les lectures `db.query(...)` et `get_display_output_value` via `run_in_threadpool` ; `log_activity` idem. Les quelques commandes qui n'ont pas besoin de la base (`play`, `pause`, `seek`, `report_position`, `cinema_*`) restent sans I/O.
- [ ] `playback_ws` : ne plus prendre `Depends(get_db)` sur toute la vie de la connexion ; ouvrir une `SessionLocal()` **par commande** dans le threadpool et la fermer aussitôt (plus aucune transaction de lecture laissée ouverte, plus de checkpoint WAL bloqué).
- [ ] Endpoints `async def` avec `db` listés en §2/C1 : passer en `def` (FastAPI les exécute dans le threadpool) sauf ceux qui doivent `await` un broadcast, pour lesquels la partie base passe en `run_in_threadpool`.
- [ ] `RetryingSession.commit` : `time.sleep` ne pose plus problème une fois que plus aucun commit n'a lieu sur la boucle ; l'assertion à ajouter en test : aucun handler `async def` ne reçoit `Session` directement (test AST simple dans `backend/tests`).
- [ ] `health` : sur le profil `android`, ne pas appeler `_kiosk_process_alive` (renvoyer `"n/a"`).
- [ ] `bobine_bootstrap.py` : `uvicorn.run(..., timeout_keep_alive=75, ws_ping_interval=None, ws_ping_timeout=None, limit_concurrency=64, backlog=128)`.

Critère de sortie : la mesure « boucle bloquée » de §4 ne montre plus de pic supérieur à 50 ms pendant une lecture réseau + un import simultanés. Suite de tests backend inchangée (39/39).

### Étape 15.3 — Diffusion WebSocket robuste (C2)

Fichiers : `backend/app/utils/ws_manager.py`, `backend/app/playback_manager.py`, `frontend/src/lib/usePlaybackSocket.ts`, `frontend/src/lib/AppSettingsContext.tsx`.

- [ ] `broadcast()` : envoi en parallèle (`asyncio.gather`) avec `asyncio.wait_for(send, timeout=1.0)` par client ; un client en dépassement deux fois de suite est fermé et retiré. La diffusion ne dépend plus du client le plus lent.
- [ ] Coalescence de `position_tick` : si un tick précédent n'a pas fini d'être envoyé, le remplacer plutôt que l'empiler (un seul tick en vol par canal).
- [ ] Keepalive tolérant : `PONG_TIMEOUT_SECONDS` porté à 60 s et, côté client, répondre au `ping` aussi depuis un `visibilitychange` (réveil immédiat quand la page redevient visible) ; envoyer un `pong` proactif toutes les 25 s côté client tant que la page est visible pour que le serveur ne dépende pas d'un minuteur gelé.
- [ ] File de commandes hors ligne : porter la fenêtre de rejeu de 5 s à 15 s pour `cinema_command` (idempotent) et garder 5 s pour `play`/`pause` (non idempotent).
- [ ] Une seule WebSocket par page : `AppSettingsContext` s'abonne à l'évènement `settings_change` via le hook `usePlaybackSocket` partagé (contexte React) au lieu d'ouvrir sa propre connexion. Divise par deux le nombre de clients.
- [ ] Accusé de réception applicatif pour `cinema_command` : `/cinema` renvoie `cinema_report` immédiatement après application (déjà fait sur `onPlay/onPause/onSeeked`) ; `/grid` et le tableau de bord affichent un état « en attente » tant que le rapport n'est pas revenu, et **rejouent** la commande une fois après 2 s sans rapport. C'est la réponse directe à S1.

Critère de sortie : sur la tablette, ouvrir l'admin dans Chrome (`MainActivity` en arrière-plan) et envoyer 20 `pause`/`play` depuis `/dashboard-cable` : 20/20 appliqués sur l'écran HDMI (vérifié par `cinema_state.playing` dans `GET`/WS), aucune ligne « sans pong » dans `technical.log`.

### Étape 15.4 — WebViews Android : cache, priorité, cycle de vie (C2, C4)

Fichiers : `MainActivity.kt`, `BobinePresentation.kt`, `BobineForegroundService.kt`, `AndroidManifest.xml`, `backend/app/main.py`.

- [x] `cacheMode = LOAD_DEFAULT` sur les deux WebViews (le serveur impose déjà la revalidation ETag ; conserver un `clearCache(false)` sur `force_reload`, déjà géré côté JS par `clearCachesAndReload`).
- [x] `BobinePresentation` : `webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false)`, `webView.onResume()` après `show()`, `webView.onPause()` à `dismiss()` ; même réglage sur `MainActivity` avec `onResume/onPause` de l'Activity.
- [x] `WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)`.
- [x] Manifeste : `android:hardwareAccelerated="true"` explicite sur `<application>` (valeur par défaut, mais figée), et `android:largeHeap="true"` (bundles + deux WebViews + CPython dans un seul processus).
- [~] Service : extension du `PARTIAL_WAKE_LOCK` à toute lecture `network` active — non faite (coût/bénéfice jugé secondaire face aux bugs trouvés ci-dessous, reste un point ouvert).
- [x] **Étape 15.4bis, ajoutée après déploiement réel sur la tablette pilote** : `RevalidateStaticFiles` (`backend/app/main.py`) corrigée — passer `cacheMode` à `LOAD_DEFAULT` a EXPOSÉ (sans le causer) un bug serveur préexistant qui rendait la revalidation ETag inopérante sur toutes les plateformes, pas seulement Android (cf. le paragraphe « Correction critique » juste au-dessus de cette section). Sans ce correctif serveur, l'étape 15.4 seule aurait activement AGGRAVÉ le problème (le cache HTTP désactivé masquait jusqu'ici la casse de la revalidation).

Critère de sortie : `chrome://inspect` sur la `Presentation` montre des 304 sur les bundles au rechargement quand le contenu est réellement inchangé, et des 200 francs quand il a changé ; `dumpsys activity processes` montre le renderer de la Presentation en `PERU` (perceptible) ou mieux avec Chrome au premier plan. **Validé sur la tablette pilote physique** (pas seulement en émulateur) : après déploiement de l'APK signé avec le correctif complet, `GET /grid/` et `GET /cinema/` reçoivent 200 (contenu neuf) au premier chargement post-mise à jour, zéro 404 en cascade, la vidéo réelle de la bibliothèque s'affiche avec sa miniature.

### Étape 15.5 — Lecture vidéo sur HDMI : variante de flux adaptée au profil (C5)

Fichiers : `backend/app/utils/video_utils.py`, `backend/app/utils/importer.py`, `backend/app/models.py`, `frontend/src/app/kiosk/page.tsx`, `frontend/src/app/cinema/page.tsx`.

- [ ] Ne pas renoncer à la conservation native (décision utilisateur) mais produire, **sur le profil Android uniquement et uniquement pour les sources au-delà de 1080p ou de 30 fps**, une **rendition secondaire** 1080p (30 ou 60 fps selon la source) `h264_mediacodec`, stockée à côté (`video_<uuid>_<titre>.1080p.mp4`, colonne `playback_file_path` nullable). Le fichier natif reste la référence, la rendition sert la lecture WebView. Encodage en tâche de fond par `ffmpeg_executor` après l'import, avec suivi dans `import_jobs` (même ETA que l'import).
- [ ] `stream_video` : paramètre `?rendition=playback` ; `/kiosk` et `/cinema` l'ajoutent quand `deployment_profile === "android"` et que la page tourne sur `127.0.0.1` (WebView). Les clients réseau (Chrome) gardent le flux natif.
- [ ] Watchdog rVFC : désarmer les micro-seeks quand `video.buffered` ne couvre pas `currentTime + 2 s` (c'est un manque de données, pas un décodeur bloqué) et ne relancer qu'un seul rattrapage par 30 s.
- [ ] `preload="auto"` déjà en place ; ajouter `video.disableRemotePlayback = true` et `playsInline` (déjà) ; vérifier que `<video>` occupe exactement la taille de l'écran HDMI (pas de mise à l'échelle CSS supplémentaire, coût GPU).

Critère de sortie : lecture d'un 4K 60 sur HDMI pendant 10 minutes sans intervention du watchdog (`console.log` compteur), CPU du renderer sous 60 % d'un cœur.

### Étape 15.6 — Cohérence de l'affichage de la bibliothèque (S5, complément)

Fichiers : `frontend/src/app/library/page.tsx`, `backend/app/routers/videos.py`.

- [ ] `PUT /api/videos/{id}` : renommer le fichier **après** le commit du titre, pas avant ; si le renommage échoue, le titre reste à jour et `file_path` inchangé (aujourd'hui un `shutil.move` lent sur FUSE retarde la réponse et, en cas d'échec, l'erreur est seulement loguée).
- [ ] Diffuser un évènement `library_change` (WS) après création/modification/suppression ; `/library`, `/grid`, `/cinema` rechargent la liste sur cet évènement au lieu du sondage à 15 s (`/cinema`, `/grid`) ou de l'absence de sondage (`/library`).
- [ ] `/library` : en cas d'échec de `fetchVideos`, conserver la liste précédente et afficher le toast (aujourd'hui `setLoading` puis liste inchangée, mais le toast d'erreur laisse croire à une disparition) ; ne jamais vider la liste sur erreur réseau.

### Étape 15.7 — Documentation, CI, publication

- [ ] `docs/plan-implementation-android.md` : section Lot 15 avec Découvertes (mesures de §4, écarts par rapport à ce plan).
- [ ] `docs/ARCHITECTURE.md` §2 et §10.2 : deux racines de stockage sur Android, WebSocket parallèle, rendition de lecture.
- [ ] `docs/releases/V3.0.3.md` (fusionné avec les correctifs seek/cinéma/imports déjà documentés sous ce numéro, jamais tagué en release stable) et `VERSION`.
- [ ] `.agents/CLAUDE.md`, `.agents/AGENTS.md`, `.gemini/state.json`.
- [ ] Test backend : aucun handler `async def` avec `Session` en paramètre direct (garde-fou C1) ; test `broadcast` avec un client bloquant (garde-fou C2).

### Estimation et séquencement

| Étape | Effort | Dépend de | Risque |
|---|---|---|---|
| 15.1 stockage | 1 jour | mesures §4 | migration de données : sauvegarde ZIP via `/api/settings/backup` avant |
| 15.2 boucle | 1 jour | aucune | régressions de typage FastAPI : couvert par la suite de tests |
| 15.3 WebSocket | 1 jour | 15.2 | comportement des miroirs : tester deux kiosks réseau |
| 15.4 WebViews | 0,5 jour | aucune | aucun |
| 15.5 rendition | 2 jours | 15.1, 15.2 | espace disque (x1,3 par cours 4K), `h264_mediacodec` disponible sur la tablette (validé au Lot 8) |
| 15.6 bibliothèque | 0,5 jour | 15.3 | aucun |
| 15.7 doc/CI | 0,5 jour | tout | aucun |

Livrer 15.1 + 15.2 + 15.4 ensemble dans une première bêta (gain attendu : S2 et S5 résolus, S1/S3/S4 nettement réduits), puis 15.3 + 15.6, puis 15.5.

---

## 6. Mission secondaire — installateur et configurateur headless (`install.sh`)

Audit de `install.sh` (v3.0.3, 1607 lignes) sur ce que le script configure « dès le début » pour les sorties audio, les pilotes et les optimisations, en mode kiosque par défaut et en mode `--no-kiosk`.

### Ce qui est correct

- Détection dynamique GPU/CPU (`lspci`/`lscpu`), activation des composants `non-free`/`non-free-firmware`, VA-API Intel (`intel-media-va-driver-non-free` avec replis) et AMD (`mesa-va-drivers`), microcode, firmware Wi-Fi.
- Groupes `render`/`video`, `Xwrapper.config`, Chromium avec `AcceleratedVideoDecodeLinuxGL` + `--use-gl=egl`.
- Audio : `Auto-Mute Mode` désactivé, démute à 100 % de tous les contrôles de toutes les cartes, chemin micro fermé, `snd_hda_intel power_save=0`, garde-fou `bobine-audio-guard.service`, drop-in `powertop`, commutation automatique de jack WirePlumber.
- NTP, mDNS avec `network-online.target`, redirection port 80, watchdog santé, sudoers restreint, canal Stable/Bêta.

### Écarts constatés

| # | Constat | Effet | Correctif proposé |
|---|---|---|---|
| H1 | La liste `apt-get install` (étape `packages`) n'installe **ni `alsa-utils`** (`amixer`, `alsactl`, `aplay`) **ni `pipewire`/`wireplumber`/`pipewire-pulse`/`pulseaudio-utils`** (`pactl`). Sur un Debian 13 minimal (netinst sans tâche bureau), aucun de ces paquets n'est présent, et toutes les commandes audio de `kiosk-xinitrc` et `bobine-audio-mute.sh` sont suffixées `|| true` ou `2>/dev/null` | Le démute, le 100 % matériel et la coupure hors session **échouent silencieusement** ; la conf WirePlumber écrite dans `/etc/wireplumber/` ne s'applique à rien ; Chromium retombe sur ALSA direct, ce qui marche par hasard tant qu'aucune autre app n'a pris la carte | Ajouter `alsa-utils` à la liste obligatoire. Trancher la pile : soit **ALSA seul** (retirer la conf WirePlumber et `pactl`, plus simple pour un kiosque mono-application), soit **PipeWire** (installer `pipewire pipewire-pulse wireplumber pulseaudio-utils`, lancer `dbus-run-session -- pipewire` + `wireplumber` en tête de `kiosk-xinitrc` avec `XDG_RUNTIME_DIR` posé, sinon aucun démon utilisateur ne tourne dans une session `xinit` lancée par systemd). Recommandation : ALSA seul en v1, PipeWire en option `--audio=pipewire` |
| H2 | `echo on > /sys/bus/pci/devices/0000:00:0e.0/power/control` : adresse PCI figée du contrôleur HDA du Wyse 5070, dupliquée dans le drop-in `powertop` | Sans effet sur tout autre mini-PC (AMD, autre Intel) | Boucle `for c in /sys/class/sound/card*/device/power/control; do echo on > "$c"; done` |
| H3 | Seul `snd_hda_intel` est traité (`power_save`). Les cartes USB (`snd_usb_audio`) et l'audio HDMI/DP ne sont pas couverts par l'anti-veille | Pops et sifflements sur DAC USB, cas fréquent hors Wyse | Ajouter `options snd_usb_audio autosuspend=... ` équivalent (paramètre `power_save` du module `snd`), et `echo on` générique ci-dessus |
| H4 | Aucune vérification à l'installation ni dans `--check` que le matériel audio et VA-API fonctionnent : la fin du script se contente de rappeler `vainfo` et `chrome://gpu` | Un déploiement peut être déclaré « terminé » avec audio muet ou décodage logiciel | Nouvelle étape `capabilities` (après `activation`) : `aplay -l` (au moins une carte), `amixer -c N scontrols` non vide, `vainfo` listant `VAProfileH264` avec le pilote attendu (`iHD`/`radeonsi`), `LIBVA_DRIVER_NAME` exporté dans `kiosk-xinitrc` si plusieurs pilotes. Résultat dans `run_end` (`"audio":ok\|fail`, `"vaapi":ok\|fail`) et dans `do_check` |
| H5 | Chromium : un seul nom de fonctionnalité (`AcceleratedVideoDecodeLinuxGL`) ; l'alias historique `VaapiVideoDecodeLinuxGL` (utilisé sur le PC de dev, cf. diagnostic du 2026-09-10) n'est pas passé ; pas de `--ignore-gpu-blocklist`, `--enable-gpu-rasterization`, `--enable-zero-copy` | Selon la version de Chromium empaquetée par Debian, le décodage matériel peut rester désactivé sans message | Passer les deux noms (`--enable-features=AcceleratedVideoDecodeLinuxGL,VaapiVideoDecodeLinuxGL`), ajouter les trois flags ; consigner le résultat de `chrome://gpu` dans l'étape `capabilities` via `chromium --headless --dump-dom chrome://gpu` |
| H6 | Aucun plafond `journald` (`SystemMaxUse`), gouverneur CPU laissé par défaut (`schedutil`/`powersave` sur Gemini Lake). **Correction après relecture complète du script** : la mise en veille d'écran (DPMS/screensaver X11, `xset s off`/`-dpms`/`s noblank`) est en réalité **déjà désactivée** dans `kiosk-xinitrc` — l'extrait lu initialement ne couvrait pas cette partie du fichier, à tort classé comme manquant | Micro-saccades sous charge, disque `/var/log` qui se remplit sur eMMC | Étape `tuning` : gouverneur CPU `performance` via un service oneshot (`/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`) ; `journald.conf.d/bobine.conf` (`SystemMaxUse=200M`). `vm.swappiness`, `sleep.target` et `unattended-upgrades` **non traités** (risque d'interaction avec une politique déjà en place sur la machine cible, non vérifiable sans matériel réel — laissés en l'état plutôt que de deviner) |
| H7 | `--no-kiosk` saute `gpu-access` et `audio` mais **installe quand même** les pilotes VA-API et le firmware | Cohérent pour un serveur sans écran, mais un `--no-kiosk` sur une machine avec écran HDMI branché n'a aucun retour audio/vidéo | Documenter que `--no-kiosk` = aucune sortie locale ; ajouter `--audio-only` si un jour un serveur sans écran doit sortir le son de la radio |
| H8 | `bobine-audio-mute.sh` et le démute de `kiosk-xinitrc` filtrent les contrôles par nom (`*Mic*`, `Capture`...) mais pas `Loopback`, `Beep`, `PCM` sur certains codecs, ni les contrôles numériques `IEC958` | Rare, mais un `IEC958` démuté à 100 % peut activer une sortie S/PDIF parasite | Étendre la liste d'exclusion : `IEC958*`, `Beep`, `Loopback` |

### Plan headless (Lot H, indépendant du Lot 15)

- [ ] H1 : paquets audio explicites + choix ALSA seul par défaut (`--audio=alsa|pipewire`), conf WirePlumber écrite uniquement en mode `pipewire`, démon lancé dans `kiosk-xinitrc`.
- [ ] H2/H3 : chemins `power/control` dynamiques, `snd_usb_audio` couvert.
- [ ] H4 : étape `capabilities` + `--check` enrichi + champs `audio`/`vaapi` dans `run_end` (l'assistant Tauri les affiche).
- [ ] H5 : flags Chromium.
- [ ] H6 : étape `tuning` (gouverneur, journald, veille, DPMS, mises à jour automatiques).
- [ ] H8 : exclusions `amixer`.
- [ ] CI : `.github/workflows/ci.yml` vérifie déjà la syntaxe et le compteur d'étapes de `install.sh` ; ajouter le nouveau nombre d'étapes et un `shellcheck`.
- [ ] Docs : `docs/ARCHITECTURE.md` §7 (options, services, étape `capabilities`), `README`.

Validation : installation à blanc sur une VM Debian 13 netinst minimale (`--dry-run` puis réelle) : `aplay -l`, `amixer`, `vainfo` disponibles et non vides après `install.sh`, `sudo ./install.sh --check` affiche les lignes audio/VA-API.
