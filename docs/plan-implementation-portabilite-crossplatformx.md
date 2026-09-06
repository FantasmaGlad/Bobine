# Plan d'implémentation — Mission PortabiliteCrossPlatformX

Statut : vérifié par cinq relectures croisées indépendantes (2026-09-06) contre
le dépôt réel — chaque relecture avait pour consigne de chercher ce qui manque,
pas de reformuler ce qui est déjà couvert. Les manques confirmés ont été
intégrés directement dans les sections concernées ci-dessous ; ce document
reflète donc déjà cette passe de vérification, pas seulement le brouillon
initial.

**Lot 0 (§1) implémenté le 2026-09-06** — code, `install.sh`,
`scripts/watchdog.sh`, touchpoints frontend et documentation associée
livrés et vérifiés (25/25 tests backend passent, import réel de l'app et
démarrage/arrêt d'un vrai processus `uvicorn --workers 1` sans erreur,
test WebSocket manuel bout en bout). Seul le test de charge sur matériel
physique reste à faire (§1.4) — hors de portée sans accès à l'appliance
réelle. Détail complet et découvertes faites en cours de route dans §1.4.

Ce document opérationnalise
les décisions de [`cahier-des-charges-multi-os.md`](cahier-des-charges-multi-os.md)
(ci-après « le CDC ») en tâches concrètes, séquencées, avec leur impact sur le
code, la documentation, le contexte des agents IA et le suivi de version. Nom
de code retenu pour l'ensemble du chantier — code, commits, branche,
communication interne — : **PortabiliteCrossPlatformX**.

Convention de suivi : chaque tâche porte une case à cocher `- [ ]`. Ce document
est vivant — cocher au fur et à mesure, ne pas le considérer figé une fois
« terminé ».

---

## 0. Principe d'organisation

Le chantier se découpe en :

- **Lot 0** (§1) — préalable architectural bloquant, touche les quatre cibles
  y compris l'appliance Linux headless actuelle.
- **Lots 1 à 3** (§2-§4) — un par nouvelle cible (Windows, Linux de bureau,
  macOS). Partagent du code commun (§5.1, `BobineTray`) mais **ne sont pas
  totalement indépendants** : plusieurs fichiers (`settings.py`,
  `updates.py`, la page Réglages, `i18n.ts`) sont modifiés par les trois —
  voir la mise en garde de coordination en fin de §5 et le séquencement §9.
- **Chantier transverse A** (§5) — adaptation du bouton Désinstaller/
  Réinitialiser et du mécanisme de mise à jour, explicitement demandé, à
  cheval sur toutes les cibles.
- **Chantier transverse C** (§6) — anti-veille sur les pages plein écran
  ouvertes hors du mode kiosque, partagée par les Lots 1-3 puisque le
  frontend l'est aussi (portée réduite le 2026-09-06, voir §6).
- **Chantier transverse B** (§7) — documentation, contexte IA, suivi
  release/site (`patch.md`).
- **Checklist exhaustive** (§8) et **séquencement** (§9), **risques** (§10)
  en fin de document pour vérifier qu'aucun fichier n'est oublié.

## 1. Lot 0 — Refonte mono-process (suppression de Redis)

Bloquant pour tout le reste (cf. CDC §4.4). À livrer et valider sur
l'appliance Linux headless actuelle **avant** d'entamer les Lots 1-3.

### 1.1 Code backend

- [x] `backend/app/utils/ws_manager.py` — remplacer le pub/sub Redis
      (`publish` ligne 249, `subscribe`/`listen` lignes 298-305) par une
      diffusion directe en mémoire aux connexions WebSocket actives du même
      process (une simple liste/`set` de connexions, plus de canal externe).
      **Attention, ce fichier porte un DEUXIÈME mécanisme Redis indépendant
      du pub/sub** : le bail distribué qui départage le kiosk « primaire »
      des kiosks « miroir » sur un même canal (`_claim_primary_lease`/
      `_release_primary_lease` lignes 137-171, `get_redis().get/set/delete`
      avec `PRIMARY_LEASE_TTL_SECONDS`/`PRIMARY_LEASE_KEY_PREFIX` lignes
      57-68, appelé par `register_kiosk`). Comme ces appels sont dans des
      `try/except Exception` larges, les laisser orphelins ne provoquerait
      aucun crash mais dégraderait silencieusement tous les kiosks en
      « toujours primaire » — réintroduisant exactement le bug multi-primaire
      que ce mécanisme corrige (cf. commentaire lignes 57-69, « correctif
      freeze vidéo en sortie réseau »). À remplacer par un dictionnaire en
      mémoire avec TTL (plus besoin de Redis : un seul process voit déjà
      toutes les connexions, donc plus de course entre workers à arbitrer).
- [x] `backend/app/scheduler_manager.py` — supprimer la synchro planning
      inter-workers (`publish` ligne 682, `_listen_schedule_sync` ligne 714,
      `subscribe` lignes 737-739) : l'état vit directement en mémoire du
      process unique, plus besoin de le republier pour qu'un autre worker le
      relise.
- [x] `backend/app/utils/video_utils.py` — remplacer le verrou global ffmpeg
      (`redis_sync.Redis`, `.lock()` lignes 45-66) par un `threading.Lock()`
      ou `asyncio.Lock()` local au process.
- [x] `backend/app/utils/tick_lock.py` — remplacer le verrou de dé-duplication
      (`SET NX PX`) par un dictionnaire en mémoire avec timestamp d'expiration.
- [x] `backend/app/utils/import_jobs.py` — remplacer la file de jobs Redis
      par une structure en mémoire (`asyncio.Queue` ou équivalent).
- [x] `backend/app/utils/redis_client.py` — supprimer le fichier (ou le vider
      de tout appel réseau) une fois plus aucun module ci-dessus ne l'importe.
- [x] `backend/app/config.py` — retirer `redis_url` de la configuration
      (ligne ~58 et le bloc `[redis]` de `config.toml`/`backend/config.toml`).
- [x] `backend/app/main.py` — retirer l'initialisation/fermeture du client
      Redis dans le `lifespan` (autour des lignes 92-135), et le passage à
      `--workers 1` (voir §1.3). **Ne pas s'arrêter au `lifespan`** : la
      fonction `health()` du même fichier (lignes ~180-209) fait
      `from app.utils.redis_client import get_redis` (ligne 20) puis
      `get_redis().ping()` pour déterminer `components["redis"]` et le champ
      `healthy` global. Si `redis_client.py` est supprimé sans retirer aussi
      cet import et ce check, le module entier plante au chargement
      (`ModuleNotFoundError`) et **le backend ne démarre plus du tout, sur
      les quatre profils y compris headless**. Retirer le champ `redis` du
      dict `components` et adapter `healthy` en conséquence.
- [x] `backend/requirements.txt` — retirer la dépendance `redis`.
- [x] `config.toml` (racine) et `backend/config.toml` — retirer la section
      `[redis]`.
- [x] `backend/app/playback_manager.py` et `backend/app/radio_manager.py` —
      **ce n'est pas une simple relecture de confirmation.** Ces deux
      fichiers contiennent leur propre logique active de persistance
      (`sync_from_redis`/`_persist_to_redis`), gatée par `BOOT_ID_REDIS_KEY`
      (`backend/app/utils/boot_state.py:34`) : ce mécanisme sert
      aujourd'hui à **reprendre l'état de lecture en cours après un
      crash-restart du backend dans le même boot machine** (par opposition à
      un vrai redémarrage/reboot, où l'état est purgé) — ce n'est donc pas
      un simple detail de synchro inter-workers, contrairement à ce que
      §1.4 affirmait initialement (« Redis ne portait aucun état
      persistant » est inexact pour ce cas précis : persistant au sens
      « survit à un crash-restart », pas au sens « survit à un vrai
      reboot »). En mono-process, ce cas de figure disparaît par
      construction (plus de source externe où relire l'état après un
      crash). **Décision explicite requise avant de clore ce point** : soit
      (a) accepter la régression fonctionnelle documentée (perte de la
      position de lecture en cours si le backend crash puis redémarre dans
      le même boot), soit (b) la remplacer par une persistance locale
      légère (ex. checkpoint périodique sur disque). Ne pas trancher
      silencieusement en supprimant juste les appels Redis.
- [x] `backend/tests/test_schedule_flow.py` (lignes 95-107) — importe
      directement `app.utils.redis_client.get_redis` et l'utilise comme
      nettoyage d'isolation entre tests (`redis.keys("schedule:firelock:*")`
      / `redis.delete(*keys)`). Une fois `redis_client.py` supprimé, ce test
      plante à la **collection** (`ImportError`), pas seulement à
      l'exécution — le critère de sortie §1.4 (« la suite de tests doit
      passer intégralement ») suppose à tort qu'un Redis simplement absent
      suffit ; ce test précis doit être réécrit (nettoyage de la structure
      en mémoire qui remplace le verrou de firelock).
- [x] `backend/app/database.py` — non fonctionnellement cassé, mais
      contient des commentaires et une tolérance de code devenus trompeurs
      une fois le mono-process en place : dimensionnement du pool
      SQLAlchemy justifié par « plusieurs workers uvicorn » (lignes 22-26),
      mode WAL/`busy_timeout` justifié pareillement (lignes 34-39), et dans
      `_migrate_add_missing_columns` une tolérance explicite aux collisions
      « duplicate column name » entre workers concurrents au démarrage
      (lignes 169-186) qui devient un vestige mort. À nettoyer par
      cohérence avec le reste du Lot 0.
- [x] Nettoyage du vocabulaire documentaire « multi-worker » au-delà des
      lignes d'appels Redis déjà listées ci-dessus : commentaires/docstrings
      dans `playback_manager.py` (`self._worker_id`, « Applique à CE worker
      un état diffusé par un AUTRE worker »), `radio_manager.py`,
      `scheduler_manager.py:448` (« Avec plusieurs workers uvicorn... »), et
      `main.py:93-114` — ce vocabulaire ne décrira plus rien de réel après
      la migration vers un état/verrou local mono-process.
- [x] `frontend/src/lib/i18n.ts:878` (FR) et `:1835` (EN) —
      `uninstallItemKeepPackages` mentionne « les paquets système (ffmpeg,
      redis…) sont conservés » : faux dès ce lot pour le profil headless
      lui-même (`install.sh` n'installera plus `redis-server`, rien à
      « conserver » à ce titre). Correctif textuel simple, indépendant du
      travail de branchement par profil prévu en §5.3.
- [x] Critère de sortie élargi : le grep de vérification finale (§1.2) doit
      porter sur **tout le dépôt** (hors `.git`/`node_modules`), pas
      seulement sur `install.sh` — c'est ce grep élargi qui aurait dû
      détecter `scripts/watchdog.sh`, `database.py`,
      `usePlaybackSocket.ts` et `cahier-des-charges-radio.md` dès la
      première rédaction de ce plan.

### 1.2 Code frontend touché par le Lot 0

- [x] `frontend/src/lib/usePlaybackSocket.ts` — `KIOSK_IDENTIFY_INTERVAL_MS
      = 5000` est calé, par commentaire explicite (lignes ~154-158), sur
      `PRIMARY_LEASE_TTL_SECONDS` (12s, backend `ws_manager.py` — cf. §1.1
      ci-dessus) : « doit rester nettement sous le TTL du bail pour ne
      jamais le laisser expirer ». Ce fichier référence Redis à 5 reprises
      (lignes 147, 163, 301, 447, 462, principalement en commentaire). À
      revoir en cohérence avec le nouveau mécanisme de bail en mémoire
      (même TTL ou nouveau, commentaires corrigés).

### 1.3 install.sh et services

- [x] `install.sh` — retirer `redis-server` de la liste de paquets apt
      (ligne ~669) et de la liste `UNITS`/dépendances liées.
- [x] `install.sh` — dans le gabarit de `bobine-backend.service` (lignes
      ~928-947), retirer `After=network.target redis-server.service` et
      `Wants=redis-server.service`, et changer `--workers 4` en `--workers 1`.
- [x] `scripts/watchdog.sh` — **fichier entier absent de la première version
      de ce plan alors qu'il est déployé en production** (unité
      `bobine-watchdog.timer`, cf. `docs/ARCHITECTURE.md:220`). Son bloc
      « Backend + Redis » (lignes 8, 11, 24-29) fait
      `systemctl is-active --quiet redis-server || systemctl restart
      redis-server` avant de redémarrer `bobine-backend` — à retirer
      entièrement. Sans ce correctif, ce script tourne toutes les 30s sur
      l'appliance headless (`OnUnitActiveSec=30s`) et tente indéfiniment de
      relancer un service qui n'existe plus, polluant le journal systemd en
      continu sur la cible même où le plan exige un comportement inchangé.
      Le bloc « logique » restant (redémarrage de `bobine-backend` si
      `/api/health` échoue, lignes 24-30 ; redémarrage de `bobine-kiosk` si
      aucun process Chromium détecté, lignes 34-38) reste, lui, pertinent et
      inchangé.
- [x] Vérifier qu'aucun autre unit systemd généré par `install.sh` ne
      référence `redis-server` **et étendre ce grep à tout le dépôt** (hors
      `.git`/`node_modules`), pas seulement à `install.sh`, avant de clore
      ce lot — c'est ce grep élargi qui aurait dû prévenir plusieurs des
      manques listés en §1.1-1.2.

### 1.4 Validation (critère de sortie du Lot 0, cf. CDC §4.4)

- [ ] **Test de charge réaliste sur l'appliance headless réelle** (Wyse ou
      équivalent) : kiosque + écran réseau + une télécommande mobile + admin
      ouvert simultanément, pendant un import vidéo en cours. **Non fait** —
      nécessite le matériel physique, hors de portée d'une implémentation
      assistée. À faire avant un déploiement en production.
- [x] Suite de tests `backend/tests/` exécutée sans Redis actif — **25/25
      tests passent** (`test_audio_flow`, `test_background_flow`,
      `test_playlist_flow` — y compris `test_playlist_waiting_period_
      auto_advances`, qui exerce directement la boucle de tick simplifiée —,
      `test_schedule_flow`, `test_video_flow`), aucun serveur Redis lancé
      pendant l'exécution.
- [x] Confirmer que `backend/tests/test_schedule_flow.py` (réécrit en §1.1)
      passe — 7/7 tests de ce fichier passent.
- [x] Non-régression fonctionnelle **partiellement** observée : import réel
      de `app.main:app` sans erreur, démarrage/arrêt propre d'un vrai
      processus `uvicorn --workers 1` (lifespan complet : watcher, scheduler,
      auto-démarrage radio, arrêt propre), `GET /api/health` → `{"status":
      "ok","components":{"database":"ok","kiosk":"ok"}}` (plus de clé
      "redis"), et un test WebSocket manuel bout en bout sur `/ws/playback`
      (connexion → `boot_id` → sync des 3 canaux → `identify` kiosque →
      `kiosk_role: {is_primary: true}` → déconnexion propre, journalisée
      correctement côté serveur). **Reste à faire** : planification réelle
      sur programmation horaire, mode coach, et télécommande mobile
      physique — non exercés par ce passage (nécessitent soit du matériel,
      soit un scénario de test plus long qu'une vérification d'implémentation).
- [x] **Décision actée sur la persistance après crash-restart** (§1.1) :
      **aucune régression, contrairement à ce que ce plan supposait par
      prudence.** Analyse du code réel : un « redémarrage d'un seul worker
      au sein du même lancement » (le seul cas où Redis faisait réellement
      la différence) n'a pas d'équivalent en mono-processus — le crash du
      seul processus existant déclenche toujours un nouveau lancement
      complet côté systemd (nouveau PID, donc nouveau `boot_id`), exactement
      le cas que `sync_from_redis()` traitait déjà comme "redémarrage complet
      du service" et pour lequel il **purgeait** l'état plutôt que de le
      reprendre (correctif "cours fantôme", déjà en place avant ce lot). La
      suppression de `sync_from_redis`/`_persist_to_redis` ne change donc
      strictement rien à ce qui se passait déjà lors d'un vrai
      crash-restart.
- [x] Aucune migration de **données** requise — confirmé : Redis ne portait
      que de l'état transitoire (position de lecture en cours, verrous),
      jamais de donnée persistante ; SQLite reste inchangé.

**Découvertes faites en cours d'implémentation, au-delà de ce que ce plan
prévoyait** (à noter pour la suite du chantier) :
- `backend/app/routers/playback.py` importait aussi `current_boot_id()`
  depuis `boot_state.py`, pour un usage **sans rapport avec Redis** (signaler
  aux clients WebSocket déjà connectés qu'un redémarrage a eu lieu, pour
  qu'ils rechargent leur page). Ce module n'a donc pas pu être supprimé
  comme prévu initialement : il a été conservé, simplifié en un simple
  identifiant aléatoire généré une fois par process (`uuid.uuid4()`), sans
  plus lire `/proc` ni dépendre de Redis.
- Plusieurs verrous que ce plan prévoyait de « remplacer par un équivalent
  en mémoire » se sont révélés **entièrement supprimables sans remplacement** :
  le verrou global ffmpeg (`video_utils.py`) fait doublon avec l'exécuteur
  `ThreadPoolExecutor(max_workers=1)` déjà existant qui sérialise seul tous
  les appels ffmpeg d'un même processus ; le verrou de déclenchement de
  planning (`scheduler_manager._acquire_fire_lock`) et les verrous de tick
  des attentes inter-cours/audio (`playback_manager.py`) protégeaient tous
  des scénarios de concurrence **entre workers**, structurellement
  impossibles avec un seul `AsyncIOScheduler`/une seule tâche asyncio par
  canal. Le bail « kiosque primaire » (`ws_manager.py`) n'a, lui, pas pu être
  supprimé (la reconnexion d'un même appareil sur un canal reste un cas réel
  même mono-processus) mais a perdu son TTL : la libération est désormais
  déclenchée de façon fiable par la vraie déconnexion locale, sans besoin
  d'expiration.
- `config.toml` (racine) et `backend/config.toml` ne contenaient en réalité
  **aucune section `[redis]`** — `redis_url` n'existait que comme valeur par
  défaut Python dans `config.py`. La tâche correspondante de ce plan
  (§1.1 initial) était donc déjà sans objet.

## 2. Lot 1 — Windows natif (`.exe`)

Priorité n°1 du CDC. Dépend du Lot 0 et du module partagé §5.1 ci-dessous.

- [ ] Créer le module partagé de détection de profil de déploiement
      (§5.1) — préalable commun aux Lots 1 à 3, à écrire une seule fois.
- [ ] **Corriger `backend/app/config.py` au-delà de la seule ligne 90** —
      remplacer le littéral POSIX `/etc/bobine/config.toml` par une
      résolution consciente de la plateforme (`%ProgramData%\Bobine\
      config.toml` sous Windows via `os.environ["ProgramData"]`,
      comportement Linux inchangé) réglait seulement le chemin de
      *recherche* du fichier de config — pas la portée réelle déjà
      arbitrée par le CDC (§5.2 : les données doivent vivre sous
      `%ProgramData%\Bobine\`, car `%ProgramFiles%\Bobine\` n'est pas
      inscriptible par un utilisateur standard sans élévation). Dans
      `load_settings()` (lignes ~142-165), **treize champs de chemins**
      (`media_dir`, `watch_dir`, `thumbnails_dir`, `backgrounds_dir`,
      `backgrounds_watch_dir`, `audio_dir`, `audio_watch_dir`, `radio_dir`,
      `radio_covers_dir`, `radio_announcements_dir`, `radio_watch_dir`,
      `branding_dir`, `logs_dir`) ainsi que `database_url` sont résolus,
      quand relatifs, contre `ROOT_DIR` (le dossier d'installation) — et le
      `config.toml` par défaut réellement livré (`backend/config.toml:14-16`,
      `config.toml` racine:6-9) utilise justement des chemins **relatifs**
      (`"data/videos"`, etc.). Si ce même fichier par défaut est embarqué
      tel quel dans l'installeur Windows, la première écriture (import
      vidéo, SQLite) échouera par manque de droits dans
      `%ProgramFiles%\Bobine\`. Il faut soit résoudre ces chemins relatifs
      contre `%ProgramData%\Bobine\` plutôt que contre `ROOT_DIR` sous
      Windows, soit livrer un `config.toml` par défaut avec des chemins
      absolus adaptés à la plateforme. Même question à trancher pour les
      Lots 2 et 3 (§3, §4 — respectivement `~/.local/share/bobine` et
      `~/Library/Application Support/Bobine`, conventions natives de
      chaque OS).
- [ ] Corriger `backend/app/utils/boot_state.py` — remplacer la lecture de
      `/proc/<pid>/stat` par `psutil.Process(os.getppid()).create_time()`
      (déjà identifié dans l'audit, nécessaire pour Windows **et** macOS).
- [ ] Corriger `backend/app/main.py:167-177` (`_kiosk_process_alive`) —
      remplacer `pgrep` par `psutil.process_iter(['name'])` pour un
      fonctionnement identique sur les trois OS.
- [ ] Écrire `BobineTray` (bibliothèque `pystray` + `Pillow`) : icône de
      zone de notification, menu (État, Ouvrir l'administration, Ouvrir en
      mode kiosque, Redémarrer, Quitter), supervision du process backend
      (relance s'il meurt). **Portée à préciser par rapport à
      `scripts/watchdog.sh`** : ce script ne se contente pas de relancer un
      process mort (déjà couvert par la relance simple ci-dessus), il
      détecte aussi des pannes *logiques* — backend vivant mais
      `/api/health` en échec, ou navigateur kiosque absent/gelé alors que le
      mode kiosque est censé tourner. Décider explicitement si `BobineTray`
      reproduit cette supervision logique (ex. poll périodique de
      `/api/health`) ou si cette capacité est sciemment abandonnée sur les
      profils desktop — ne pas le laisser tomber par simple omission.
- [ ] Intégrer un répondeur mDNS embarqué (lib `zeroconf`) démarré par le
      backend lui-même, publiant `bobine.local` — best-effort, non bloquant
      en cas d'échec.
- [ ] Implémenter le lancement du mode kiosque optionnel depuis le menu du
      tray : navigateur par défaut ou Edge avec
      `--kiosk --autoplay-policy=no-user-gesture-required`, et
      `SetThreadExecutionState` activé **seulement** pendant cette session
      (pas globalement).
- [ ] Adapter le endpoint de désinstallation/réinitialisation pour ce
      profil (détail complet en §5), **et le mécanisme de mise à jour**
      (le flux « Vérifier/Appliquer une mise à jour » existant repose
      entièrement sur `git` — voir §5.4, nouvelle sous-section).
- [ ] Règle de pare-feu Windows Defender pour le port d'écoute backend
      (le backend écoute sur `0.0.0.0`, cf. `install.sh:862,939` et
      README « télécommande depuis n'importe quel téléphone du LAN ») :
      sans règle explicite (`netsh advfirewall firewall add rule` posée par
      l'installeur, ou au premier lancement), la première ouverture de
      socket non-loopback déclenche l'invite native Windows « Autoriser
      l'accès ? » — souvent laissée sur « non » côté réseaux « Public »
      (profil par défaut de nombreuses connexions Wi-Fi domestiques). Sans
      cette règle, la télécommande mobile — fonctionnalité phare mise en
      avant par le marketing — peut ne simplement pas fonctionner, sans
      message d'erreur clair pour l'utilisateur (juste un timeout côté
      téléphone). À documenter dans l'écran de fin d'installation si la
      règle ne peut pas être posée automatiquement.
- [ ] Spec PyInstaller : générer `BobineBackend.exe` et `BobineTray.exe`,
      mode *onedir* recommandé au démarrage du chantier (plus simple à
      déboguer que *onefile*, à reconsidérer une fois stabilisé).
- [ ] Fournir `ffmpeg.exe`/`ffprobe.exe` (builds statiques gyan.dev/BtbN)
      à côté de l'exécutable — aucune adaptation de code requise, les appels
      backend sont déjà par nom nu.
- [ ] Écrire le script Inno Setup (`.iss`) : `[Files]` (exécutables,
      `frontend/out/`, `config.toml` par défaut adapté aux chemins
      `%ProgramData%` — voir le correctif `config.py` ci-dessus),
      `[Icons]` (raccourci Démarrage, Menu Démarrer), `[Registry]` (entrée
      « Applications et fonctionnalités »), la règle de pare-feu ci-dessus,
      gestion de l'UAC si nécessaire à l'installation.
- [ ] **Section `[Languages]` de l'installeur** — l'app démarre en
      français par défaut (`DEFAULT_LANGUAGE = "fr"`,
      `AppSettingsContext.tsx:68`, aucune détection de langue navigateur/OS)
      mais un script Inno Setup sans `[Languages]` explicite s'affiche
      uniquement en anglais par défaut : ajouter au moins FR + EN pour ne
      pas livrer un assistant d'installation dans une langue différente de
      celle de l'application elle-même.
- [ ] **Décision explicite sur la licence** — le dépôt contient un fichier
      `LICENSE` à la racine ; Inno Setup supporte nativement
      `LicenseFile=` dans `[Setup]` pour l'afficher/faire accepter à
      l'installation. Décider consciemment de l'inclure ou de l'omettre,
      plutôt que de laisser ce choix par défaut.
- [ ] Icône d'application au format `.ico` (multi-résolution) — à produire
      à partir des assets existants (`Assets/Images/`).
- [ ] CI : ajouter un job `windows-latest` à `.github/workflows/ci.yml`
      pour builder l'exécutable PyInstaller et l'installeur Inno Setup à
      chaque push (rappel : PyInstaller ne cross-compile pas, ce job doit
      tourner sur un runner Windows réel).
- [ ] Test manuel sur machine Windows réelle : installation propre,
      lancement au démarrage de session, mode kiosque, mDNS, désinstallation
      via « Applications et fonctionnalités », avertissement SmartScreen
      documenté et accepté comme limitation connue (CDC §5.6, décision #7).
- [ ] Documentation : nouvelle section README « Installer sur Windows »
      (§7.1).

## 3. Lot 2 — Linux non-headless (`.deb`)

Dépend du Lot 0 et du module partagé §5.1. Réutilise directement le code
Python et le `BobineTray` du Lot 1 (seul le packaging change).

- [ ] Réutiliser tel quel `BobineTray` (`pystray`, backend GTK/AppIndicator
      sous Linux) — aucun nouveau code de tray à écrire.
- [ ] Choisir l'outil de paquet : `fpm` (rapide à mettre en place) ou
      `dpkg-deb`/`debhelper` (plus proche des conventions Debian) — trancher
      en ouverture de ce lot (cf. CDC §12, question encore ouverte).
- [ ] Structure du paquet : `usr/lib/bobine/` (backend + venv ou
      dépendances déclarées, à trancher — CDC §12), `usr/share/applications/
      bobine.desktop`, `etc/systemd/user/bobine.service` (unité **utilisateur**,
      pas système — différence clé avec l'appliance headless).
- [ ] Fichier `control` : dépendances déclarées (`ffmpeg`, `python3`,
      environnement graphique), architecture `amd64` (cohérent avec le
      matériel visé, cf. `cahier-des-charges-installeur.md:155`).
- [ ] mDNS : réutiliser `avahi-daemon` s'il est déjà actif sur le poste
      (cas fréquent en environnement de bureau Debian/Ubuntu), sinon retomber
      sur le même répondeur `zeroconf` embarqué que Windows/macOS.
- [ ] Résoudre les chemins de données par défaut vers
      `~/.local/share/bobine` (convention XDG) plutôt que contre le dossier
      d'installation — même problème de fond que celui identifié pour
      Windows (§2, correctif `config.py`) : `usr/lib/bobine/` est
      typiquement possédé par `root` via `dpkg`, pas inscriptible par
      l'utilisateur courant.
- [ ] Adapter le endpoint de désinstallation/réinitialisation pour ce
      profil (§5) **et le mécanisme de mise à jour** (§5.4) — sur ce
      profil, `apt remove`/mise à jour via dépôt sont les voies naturelles,
      le flux `git pull` actuel n'a pas plus de sens ici que sur Windows.
- [ ] Scripts de maintenance du paquet (`postinst`/`prerm`/`postrm`) :
      activer/désactiver l'unité systemd utilisateur au bon moment du cycle
      de vie `dpkg`.
- [ ] CI : job de build `.deb` + `lintian` (linter standard Debian) pour
      détecter les erreurs de packaging avant publication.
- [ ] Test manuel sur Debian 12/13 et Ubuntu LTS récent, environnement
      GNOME par défaut (cf. CDC §12) : installation, lancement, tray,
      kiosque optionnel, désinstallation via `apt remove`.
- [ ] Documentation : nouvelle section README « Installer sur Linux
      (bureau) », avec la distinction explicite vis-à-vis de l'appliance
      headless (§7.1).

## 4. Lot 3 — macOS (plus tard)

Dépend du Lot 0 et du module partagé §5.1. Réutilise le code Python et
`BobineTray` des lots précédents.

- [ ] **Lever explicitement l'ambiguïté `pystray` vs `rumps` avant de
      démarrer.** Le CDC et ce plan présentent `BobineTray` comme un
      module écrit une seule fois puis réutilisé sans changement sur les 3
      OS (`pystray` sait en principe sélectionner un backend adapté par
      plateforme). Mais macOS est parfois évoqué séparément via `rumps`
      (paquet PyPI distinct, API de construction de menu différente). Si
      `rumps` s'avère réellement nécessaire, ce n'est plus une simple
      réutilisation : cela implique une dépendance supplémentaire
      (`rumps`/`pyobjc`) à ajouter à `requirements.txt` et aux
      hidden-imports PyInstaller macOS, non budgétée ailleurs dans ce plan.
      À trancher en tout début de ce lot, pas découvert en cours de route.
- [ ] Bundle `.app` via PyInstaller (cible macOS — nécessite de tourner
      sur une vraie machine macOS, pas de cross-compilation depuis Linux/
      Windows) ou `py2app`.
- [ ] Icône au format `.icns` — à produire à partir des assets existants.
- [ ] Fichier `Info.plist` du bundle (identifiant, version, nom d'affichage).
- [ ] Résoudre les chemins de données par défaut vers
      `~/Library/Application Support/Bobine` plutôt que contre le bundle
      `.app` (lecture seule / sujet à la translocation Gatekeeper) — même
      problème de fond que Windows (§2) et Linux bureau (§3).
- [ ] LaunchAgent (`~/Library/LaunchAgents/com.bobine.app.plist`) : `Label`,
      `ProgramArguments`, `RunAtLoad=true`, `KeepAlive` conditionné (relance
      sur crash, pas sur sortie propre), `StandardOutPath`/`StandardErrorPath`
      pour les logs.
- [ ] `BobineTray` (menu bar) : mêmes items de menu que Windows/Linux (cf.
      point d'ambiguïté ci-dessus sur le backend exact).
- [ ] mDNS : aucune action, Bonjour est actif nativement.
- [ ] Mode kiosque optionnel : Chrome `--kiosk` + `caffeinate -d -i -w <pid>`
      actif uniquement pendant la session kiosque.
- [ ] Pare-feu applicatif macOS (« Voulez-vous autoriser les connexions
      entrantes ? ») — même remarque que pour Windows (§2) : sans
      autorisation, la télécommande mobile peut ne pas fonctionner. Moins
      critique que sous Windows (l'invite macOS est plus systématiquement
      acceptée par les utilisateurs) mais à documenter tout de même.
- [ ] Adapter le endpoint de désinstallation/réinitialisation pour ce
      profil (§5) **et le mécanisme de mise à jour** (§5.4).
- [ ] Fabrication du `.dmg` de distribution (`hdiutil` ou `create-dmg`) avec
      glisser-déposer vers `/Applications`.
- [ ] CI : job `macos-latest` pour builder le bundle à chaque push.
- [ ] Test manuel sur Mac réel : installation, LaunchAgent actif au login,
      tray, kiosque optionnel, désinstallation (glisser vers la Corbeille +
      suppression du LaunchAgent), avertissement Gatekeeper documenté comme
      limitation connue (CDC §7.4, décision #7).
- [ ] Documentation : nouvelle section README « Installer sur macOS »
      (§7.1).

## 5. Chantier transverse A — Bouton Désinstaller / Réinitialiser

Demande explicite : adapter `backend/app/routers/settings.py`
(`_run_full_reset`/`reset_system` lignes 484-524, `_run_uninstall`/
`uninstall_system` lignes 538-576) pour qu'il se comporte correctement selon
la méthode d'installation, **en préservant à l'identique le comportement
actuel pour le mode headless**.

### 5.1 Module de détection de profil (préalable partagé, Lots 1-3)

- [ ] Créer un petit module (ex. `backend/app/utils/deployment.py`) exposant
      une fonction `get_deployment_profile() -> Literal["linux-headless",
      "linux-desktop", "windows", "macos"]`, détectée via `platform.system()`
      combiné à la présence de `UNINSTALL_WRAPPER`/`SUDOERS_FILE` (ligne
      530-531 de `settings.py`) pour distinguer spécifiquement
      `linux-headless` de `linux-desktop` (les deux tournent sous Linux, seul
      l'artefact d'installation posé par `install.sh` les différencie).
- [ ] Exposer ce profil dans `GET /api/settings` (nouveau champ
      `deployment_profile`), pour que le frontend puisse adapter le texte et
      le comportement du bouton sans dupliquer la logique de détection.
- [ ] **Éviter par construction la collision à 4 fichiers identifiée en
      §9** : ne pas coder un `if/elif` par profil directement dans
      `settings.py`/`updates.py` (bloc que les 3 lots devraient chacun venir
      éditer). Définir à la place, dans ce même module, une petite
      abstraction — un protocole/classe `ProfileHandler` avec les méthodes
      `restart()`, `uninstall()` (renvoie soit une action directe, soit un
      texte d'instruction) et `check_update()`/`apply_update()` — puis un
      registre `PROFILE_HANDLERS: dict[str, ProfileHandler]`. `settings.py`
      et `updates.py` n'appellent alors **qu'une seule fois, ici même**,
      `get_profile_handler().restart()` etc. — ces deux fichiers ne sont
      plus modifiés par les Lots 1-3, qui se contentent chacun d'**ajouter**
      un nouveau fichier (`deployment_windows.py`, `deployment_linux_
      desktop.py`, `deployment_macos.py`) implémentant l'interface, sans
      jamais toucher au même bloc de code qu'un autre lot. Le handler
      `linux-headless` (comportement actuel, inchangé) est écrit dans ce
      même Lot A, à partir du code existant de `settings.py`/`updates.py`.
- [ ] Même logique côté frontend : plutôt qu'un bloc JSX unique avec un
      `switch(deploymentProfile)` que chaque lot viendrait enrichir,
      structurer `frontend/src/app/settings/page.tsx` pour qu'il rende un
      composant par profil (`<HeadlessUninstallPanel/>`,
      `<DesktopUninstallPanel profile="windows"/>`, etc.) et que les textes
      i18n soient organisés **par profil** dès le départ (ex. clés
      `uninstall.windows.hint`, `uninstall.macos.hint` plutôt que des clés
      plates réutilisées par tous) — une **addition** de nouvelles clés/un
      nouveau composant par lot ne crée pas de conflit de fusion, contrairement
      à l'édition répétée des mêmes lignes.

### 5.2 Réinitialisation complète (`_run_full_reset`)

- [ ] **Profil `linux-headless`** : comportement **inchangé** — diffusion
      `force_reload` puis `sudo systemctl restart` sur `bobine-kiosk` et
      `bobine-backend` (lignes 506-511 actuelles, à ne pas toucher).
- [ ] **Profils `windows`/`linux-desktop`/`macos`** : pas de service
      système à redémarrer dans ce modèle — la réinitialisation devient
      « diffuser `force_reload` puis demander au `BobineTray` local de
      relancer le process backend » (mécanisme à définir avec le Lot 1,
      §2 : le tray expose déjà une action « Redémarrer », la réutiliser plutôt
      que d'en écrire une seconde).

### 5.3 Désinstallation complète (`_run_uninstall`/`uninstall_system`)

- [ ] **Profil `linux-headless`** : comportement **inchangé**, y compris le
      message d'erreur 400 actuel si l'enveloppe/sudoers sont absents
      (lignes 566-573) — c'est explicitement le cas « poste de dev », à ne
      pas casser.
- [ ] **Profil `windows`** : le bouton ne doit **pas** tenter de désinstaller
      lui-même l'application (pas d'équivalent sûr à l'enveloppe
      `systemd-run` actuelle sans risquer de tuer le process qui exécute la
      requête). À la place : ouvrir la page système
      `ms-settings:appsfeatures` (ou afficher une instruction textuelle si
      l'ouverture échoue) et rediriger l'utilisateur vers le vrai
      désinstalleur généré par Inno Setup.
- [ ] **Profil `linux-desktop`** : même logique — pas de tentative de
      `apt remove` déclenchée depuis le backend (nécessiterait une élévation
      `pkexec` peu fiable en contexte web). Afficher l'instruction
      (« Utilisez votre gestionnaire de paquets : `sudo apt remove bobine` »).
- [ ] **Profil `macos`** : même logique — instruction (« Quittez Bobine,
      supprimez `Bobine.app` du dossier Applications »), pas d'automatisation
      côté backend.
- [ ] Frontend `frontend/src/app/settings/page.tsx` (section autour des
      lignes 840-925) : le texte et le bouton (`uninstallHint`,
      `uninstallItemServices`, `uninstallItemApp`, `uninstallItemData`,
      `uninstallItemKeepPackages`, clés i18n dans `frontend/src/lib/i18n.ts`)
      doivent se brancher sur `deployment_profile` (§5.1) — bouton d'action
      directe uniquement pour `linux-headless`, bloc d'instructions pour les
      trois autres profils.
- [ ] `backend/app/routers/updates.py` (lignes 180-185) — même pattern
      `sudo systemctl restart` après une mise à jour : appliquer exactement
      la même branche par profil que §5.2 (redémarrage via le tray pour les
      profils desktop), pour ne pas dupliquer une seconde fois la logique de
      redémarrage en plus de celle de `settings.py`. **Ce n'est qu'une
      partie du problème** — voir §5.4 ci-dessous, le reste de ce fichier
      dépend de `git` bien plus largement que ce seul redémarrage.

✅ **Risque de collision entre lots — résolu par construction, pas par
coordination** : sans précaution, `settings.py` (§5.2/§5.3), `updates.py`
(ci-dessus et §5.4), `frontend/src/app/settings/page.tsx` et `frontend/
src/lib/i18n.ts` seraient modifiés par les **trois** Lots 1/2/3 dans les
mêmes fonctions/blocs (un `elif` par profil ajouté par chacun). Plutôt que
de compter sur une coordination humaine (rebase planifié, un lot à la
fois), §5.1 ci-dessus élimine le problème à la racine : ces quatre fichiers
ne sont édités **qu'une seule fois**, au moment où §5.1 est écrit (pose de
l'abstraction `ProfileHandler`/composants par profil), avec le handler
`linux-headless` comme seule implémentation initiale. Chaque Lot 1/2/3
**ajoute ensuite un nouveau fichier** (handler backend + composant/clés
i18n frontend) sans plus jamais toucher à `settings.py`, `updates.py` ou au
bloc JSX partagé — une addition de fichier ne crée pas de conflit de
fusion, contrairement à l'édition répétée des mêmes lignes. Les Lots 1/2/3
peuvent donc réellement avancer en parallèle sur ce point précis, à
condition que §5.1 soit livré en premier.

### 5.4 Mécanisme de mise à jour (`updates.py`) — dépendance à `git` bien
plus large que le seul redémarrage

Le plan initial ne corrigeait que la toute fin de `_run_update_pipeline`
(le `sudo systemctl restart`, §5.3 ci-dessus). En réalité, **tout le
mécanisme** « Vérifier/Appliquer une mise à jour » visible dans les
Réglages (boutons et bannière, `frontend/src/app/settings/page.tsx` autour
des lignes 336, 361, 680-749) repose sur un dépôt git présent au chemin
d'exécution — absent par construction sur un `.exe` PyInstaller, un bundle
`.app` ou un paquet `.deb` installé :

- [ ] `_get_local_version_info()` (`updates.py` lignes ~34-75) fait
      `git rev-parse --short HEAD` et `git describe --tags` sur `repo_dir` —
      échouera silencieusement et retombera sur le littéral figé
      `"V2.0.1"` (ligne 38, dupliqué comme valeur par défaut côté frontend
      à `settings/page.tsx:706`) sur les trois nouveaux profils : la
      version affichée resterait bloquée en permanence.
- [ ] `_run_update_pipeline()` (lignes ~143-183) fait un `git pull
      --ff-only` en première étape (lignes 158-165) — n'a de sens que sur
      l'appliance headless (dépôt git cloné par `install.sh`). Sur les
      profils desktop, cette étape doit être retirée/remplacée, pas
      seulement le redémarrage qui la suit.
- [ ] **Décision de produit requise** (le CDC §12 note déjà l'auto-update
      desktop comme « non cadré, à spécifier séparément » — mais il s'agit
      ici d'un mécanisme qui **existe déjà et doit être désactivé/adapté**,
      pas seulement d'une fonctionnalité absente à concevoir) : pour les
      profils `windows`/`linux-desktop`/`macos`, soit masquer entièrement
      le bouton « Vérifier une mise à jour » et rediriger vers la page des
      GitHub Releases, soit lui donner un sens minimal (comparer la version
      embarquée à la dernière release GitHub, sans jamais tenter de `git
      pull`). Ne pas laisser un bouton visuellement actif échouer en
      silence.

### 5.5 Sauvegarde et restauration avant une action destructrice

`uninstall_system` (§5.3) déclenche une suppression **irréversible** de
« TOUTES les données » (`settings.py:554,557`). Les seuls outils de
sauvegarde/restauration du projet, `scripts/backup.sh` et
`scripts/restore.sh`, sont strictement Linux/systemd/bash : ils testent
`systemctl is-active bobine-backend` (`restore.sh:21`), codent en dur
`/etc/bobine/config.toml` (`backup.sh:55`, `restore.sh:65` — chemin déjà
identifié comme non universel au §2) et dépendent de la commande CLI
`bobine` définie uniquement par `install.sh` (lignes 887-904, absente sur
les profils desktop).

- [ ] Décider explicitement ce que devient la sauvegarde/restauration pour
      les profils `windows`/`linux-desktop`/`macos` **avant** de livrer le
      Chantier A sur ces profils — a minima, un script ou une commande de
      tray (« Exporter mes données ») qui archive le dossier de données
      (§2/§3/§4) en un `.zip`, réutilisable pour une restauration manuelle
      après réinstallation.

## 6. Chantier transverse C — Expérience utilisateur du profil app de bureau

> **Correction du 2026-09-06** (retour du porteur du projet) : les deux
> constats initialement listés ici (modèle « écran câblé/réseau » soi-disant
> inadapté à un poste unique, et absence supposée de parcours de connexion
> mobile) reposaient sur une **mauvaise compréhension de l'architecture** —
> ce ne sont **pas** des angles morts. Le vrai workflow, désormais explicite
> en [CDC §3.1](cahier-des-charges-multi-os.md#31-le-modèle-administrateur--sorties-câblé-réseauradio-est-inchangé-dans-les-deux-familles--précision-apportée-le-2026-09-06) :
> l'**administrateur** (une seule URL, consultable au format téléphone ou
> PC) sert à **contrôler trois sorties** — câblé, réseau, **et radio** (que
> ce plan avait omise dans sa première version) —, chacune ayant son propre
> écran dédié. Cette séparation administrateur/sorties est le cœur du
> produit et **ne change pas** avec le passage au profil app de bureau : le
> mode kiosque optionnel (décision #1) porte uniquement sur le verrouillage
> plein écran d'une sortie, pas sur ce modèle. Le mécanisme existant de
> connexion au téléphone (URL affichée dans Réglages,
> `network.local_ip`/`network.mdns_url`) couvre donc déjà le cas d'usage
> « connecter mon téléphone » sur les trois nouvelles cibles — aucun
> nouveau parcours à concevoir. Les tâches correspondantes ont été
> retirées de ce plan ; ce chantier ne porte donc plus que sur l'anti-veille
> ci-dessous.

### 6.1 Anti-veille non couplé aux pages plein écran elles-mêmes

- [ ] L'anti-veille (`SetThreadExecutionState`/`xset`/`caffeinate`,
      CDC §5.4/§6.3/§7.2) n'est prévu que pour l'action de menu « Ouvrir en
      mode kiosque » du tray. Mais `/cinema`, `/radio`, `/coach`, `/kiosk`
      restent des routes plein écran ordinaires (`isFullscreenRoute`,
      `frontend/src/components/ClientLayout.tsx:41-48`), atteignables par
      simple navigation dans un onglet — exactement l'usage que le kiosque
      *optionnel* encourage. Dans ce cas, aucune des briques d'anti-veille
      prévues ne s'active : l'écran peut s'éteindre en pleine diffusion.
- [ ] Évaluer l'ajout de la **Screen Wake Lock API** (standard web,
      `navigator.wakeLock.request("screen")`) directement dans ces pages
      côté frontend — indépendante du mode de lancement (tray ou onglet
      classique), donc pertinente pour les 3 profils desktop sans dupliquer
      de logique par OS.

## 7. Chantier transverse B — Documentation, contexte IA, suivi release/site

### 7.1 README.md / README.fr.md

- [ ] Corriger la revendication HDMI-CEC (lignes 38 et 205, FR et EN) —
      décision #4 du CDC : l'extinction TV repose sur la veille automatique
      native du téléviseur, pas sur une commande logicielle Bobine.
- [ ] Réécrire la section « Quick start » pour distinguer clairement les
      quatre chemins d'installation (appliance headless via `install.sh`,
      Windows via `.exe`, Linux de bureau via `.deb`, macOS via `.dmg`), avec
      un lien vers le CDC pour le détail architectural.
- [ ] **Trois autres passages, hors Quick start, affirment encore
      l'architecture multi-worker + Redis** et ne sont couverts par aucun
      correctif ci-dessus : la puce fonctionnalité « Local-first and
      resilient — multi-worker backend, shared state… » (~ligne 64), la
      section « How it works » qui dit littéralement « a FastAPI backend
      (multi-worker) with Redis as a shared state bus » (~ligne 73), et la
      section santé/monitoring qui dit que `/api/health` « reports the
      status of Redis » et que le watchdog redémarre « backend, Redis or
      kiosk » (~ligne 177). Identique mot pour mot en FR. À corriger en
      cohérence avec le Lot 0.
- [ ] Mettre à jour les badges de plateforme en tête de document
      (actuellement uniquement « Platform: Debian 13 »).
- [ ] Ajouter une note dans « Hardware requirements » précisant que ces
      contraintes (mini PC dédié, VA-API…) concernent le profil appliance ;
      le profil app de bureau tourne sur le PC/Mac déjà possédé par
      l'utilisateur.

### 7.2 docs/ARCHITECTURE.md

- [ ] Le **résumé d'ouverture du document, avant le Sommaire** (donc hors
      de toute section numérotée) affirme « Serveur multi-worker FastAPI +
      Redis + SQLite... » et « le modèle de données inter-workers » — une
      revue faite strictement section par section laisserait ces deux
      phrases intactes puisqu'elles ne portent aucun numéro. À corriger en
      premier, avant les sections ci-dessous.
- [ ] §1 « Stack et démarrage » — retirer la mention de Redis et du
      multi-worker comme faits acquis (post Lot 0).
- [ ] §2 « Architecture générale (Multi-worker & Bus Redis) » — titre et
      contenu à réécrire entièrement : ce n'est plus multi-worker, il n'y a
      plus de bus Redis. Décrire le nouveau modèle mono-process.
- [ ] §7 « Script d'installation & Services systemd » — **ne pas se
      contenter d'une clarification de périmètre** : cette section contient
      des faits qui restent faux même pour le profil headless après le
      Lot 0 — « bobine-backend.service : API FastAPI Uvicorn sur le port
      8000 (4 workers) », le watchdog qui « relance de redis-server (si
      arrêté) puis de bobine-backend », et `/api/health` qui renverrait
      encore `{"components": {"redis", "database", "kiosk"}}`. Corriger ce
      contenu **et** ajouter le renvoi de périmètre vers ce plan pour les
      trois autres profils.
- [ ] §8 « Référence API HTTP & WebSockets » — la table `GET /api/settings`
      doit gagner une ligne pour le nouveau champ `deployment_profile`
      (§5.1), sans quoi la référence API reste incomplète vis-à-vis du
      nouveau contrat.
- [ ] §9 « Exploitation & Découverte Réseau (Wyse) » — même clarification :
      section spécifique au profil headless, pas généraliste.
- [ ] Table des matières (sommaire en tête de fichier) à resynchroniser
      après ces changements de structure.

### 7.3 Cahiers des charges existants

- [ ] `docs/cahier-des-charges-installeur.md` — ajouter une ligne en tête
      de document précisant explicitement que son périmètre est désormais le
      profil **Linux headless uniquement** (c'était déjà implicite, ce
      chantier le rend nécessaire à expliciter).
- [ ] `docs/cahier-des-charges-multi-os.md` — au fur et à mesure que les
      questions ouvertes de son §12 se tranchent pendant l'implémentation
      (outil de freeze, lib de tray, port par défaut…), reporter la décision
      actée dans le CDC lui-même pour qu'il reste la source de vérité à jour.
- [ ] **`docs/cahier-des-charges-radio.md` — absent de la première version
      de cette liste.** Ce CDC de 372 lignes, activement référencé comme
      « cahier des charges complet » du module Radio depuis
      `docs/ARCHITECTURE.md` §5, affirme en toutes lettres (lignes 139, 142)
      que l'état du canal radio vit « dans Redis (bus d'état partagé...) »
      — affirmation fausse après le Lot 0. Ce n'est pas un document mort à
      ignorer : c'est une référence vivante à corriger au même titre que
      les deux autres.

### 7.4 patch.md (racine) — suivi site web et releases

> ⚠️ Deux fichiers portent le même nom `patch.md` dans ce dépôt :
> `/patch.md` (« Notes de version & Correctifs », **celui visé par cette
> section**) et `docs/patch.md` (« branding, animation de lancement... »,
> sans rapport avec ce chantier). Vérifier qu'on édite le bon avant toute
> modification.

Ce fichier suit une convention établie (une section numérotée par lot de
changements livré, avec sous-section « Modifications techniques »). Ce
chantier étant un programme pluri-semaines et non un patch de session, il
ne doit **pas** être inliné entièrement dans `patch.md` — proposer plutôt,
à chaque Lot livré (0 à 3), une section courte qui pointe vers le CDC et ce
plan, et qui liste précisément **l'impact site web / releases GitHub** :

- [ ] **À la livraison du Lot 0** : aucun impact site (changement interne),
      mais noter le changement d'architecture dans les notes de la prochaine
      release (mention « suppression de la dépendance Redis » utile pour
      quiconque aurait scripté une supervision externe autour de Redis).
- [ ] **À la livraison du Lot 1 (Windows)** : ajouter sur le site
      (bobine.fit) un lien de téléchargement `.exe` et un badge « Windows »
      dans le tableau des plateformes supportées ; joindre le `.exe` comme
      asset de la prochaine GitHub Release ; mettre à jour le corps des
      notes de release avec les instructions d'installation Windows et
      l'avertissement SmartScreen attendu (décision #7).
- [ ] **À la livraison du Lot 2 (Linux bureau)** : lien de téléchargement
      `.deb` sur le site, asset joint à la release, notes de release mises à
      jour (distinction avec l'appliance headless).
- [ ] **À la livraison du Lot 3 (macOS)** : lien `.dmg` sur le site, asset
      de release, notes mentionnant l'avertissement Gatekeeper attendu.
- [ ] **Correction HDMI-CEC** (§7.1) : si le site public reprend la même
      revendication marketing que le README (à vérifier au moment de
      l'exécution de cette tâche), la corriger au même moment.

### 7.5 Contexte des agents IA

Ces fichiers orientent tout agent IA démarrant une session sans historique
— ils contiennent aujourd'hui des informations **fausses ou obsolètes**
indépendamment de ce chantier, à corriger dans tous les cas :

- [ ] `.gemini/AGENTS.md:4` et `.gemini/state.json` (`project`,
      `space.local.path`, `space.production_wyse.path`) référencent encore
      l'ancien nom/chemin de projet `OpenLesmillsCinema` au lieu de
      `Bobine` — **bug préexistant, sans rapport avec ce chantier, à
      corriger immédiatement**. **La même erreur existe aussi dans
      `.agents/AGENTS.md:35` et `.agents/CLAUDE.md:47`** (table
      « Cartographie Spatiale/Espatiale », ligne « Développement Local ») —
      omis de la liste initiale alors que ce sont les deux fichiers
      d'orientation les plus consultés (`CLAUDE.md` s'ouvre littéralement
      par « guide de référence d'orientation autonome pour tout agent
      AI ») ; à corriger dans le même geste.
- [ ] `.gemini/state.json` (`space.production_wyse.systemd_services`)
      liste encore `openlesmillscinema-backend.service` etc. au lieu des
      vrais noms `bobine-*` — même remarque.
- [ ] `.agents/CLAUDE.md` et `.agents/AGENTS.md` référencent un fichier
      `.agents/STATE.md` qui **n'existe pas** dans le dépôt — soit le créer,
      soit retirer la référence, indépendamment de ce chantier.
- [ ] Une fois le Lot 0 livré : retirer la règle « Préserver le modèle
      multi-worker Uvicorn + bus d'état Redis » (`.agents/AGENTS.md` §1.5,
      `.agents/CLAUDE.md` §2) — elle devient **incorrecte** et risquerait de
      faire annuler par erreur le travail de ce chantier par un futur agent
      qui la suivrait à la lettre.
- [ ] Une fois les Lots 1-3 livrés : étendre la table « Cartographie
      Spatiale » (`.agents/CLAUDE.md` §1, `.agents/AGENTS.md` §2) avec les
      nouveaux profils de déploiement, et clarifier explicitement que la
      ligne « Production Wyse » ne décrit que le profil appliance headless,
      pas « la » production.
- [ ] `.gemini/state.json` — champ `last_commit`/`features_completed` très
      obsolète (référence un commit `aa075c9` largement antérieur à ce
      chantier) : à rafraîchir une fois ce chantier terminé, ou envisager de
      retirer ce mécanisme de recopie manuelle d'état s'il n'est plus
      entretenu de façon fiable (question à trancher avec le porteur du
      projet, hors du strict périmètre de ce chantier mais soulevée ici
      puisqu'elle a été découverte pendant l'audit de ce plan).

### 7.6 CI (`.github/workflows/ci.yml`) et scripts divers

- [ ] Ajouter les jobs `windows-latest` (Lot 1) et `macos-latest` (Lot 3),
      en plus du job Linux existant.
- [ ] Ajouter un job de build/lint `.deb` (Lot 2, `lintian`).
- [ ] Une fois le Lot 0 livré, reconsidérer l'ajout de la suite
      `backend/tests/` à la CI (mentionnée comme actuellement absente à
      cause de la dépendance Redis, cf. commentaire en tête du fichier) —
      amélioration désormais possible, pas obligatoire pour ce chantier.
- [ ] `scripts/migrate_unify_data_dirs.py` (docstring lignes 31-35) —
      documente encore une procédure d'exécution manuelle via
      `sudo systemctl stop/start bobine-backend`. Script ponctuel de
      migration historique ; incertain qu'il serve encore pour une
      installation neuve (`install.sh` écrit déjà la structure unifiée
      d'après son propre docstring). À trancher explicitement (le corriger
      ou le retirer) plutôt que de le laisser avec des instructions qui
      deviennent fausses sur les profils bureau.

## 8. Checklist exhaustive (vue transverse anti-oubli)

Récapitulatif à plat de tout ce qui est touché, organisé par nature plutôt
que par lot, pour une dernière passe de vérification avant de considérer le
chantier terminé.

**Code backend** : `ws_manager.py` (pub/sub **et** bail primaire),
`scheduler_manager.py`, `video_utils.py`, `tick_lock.py`, `import_jobs.py`,
`redis_client.py`, `config.py` (`redis_url` **et** les 13 champs de chemins
de données), `main.py` (`lifespan` **et** `health()`), `boot_state.py`,
`database.py` (commentaires/code mort), `playback_manager.py`,
`radio_manager.py` (décision de persistance crash-restart), `settings.py`,
`updates.py` (redémarrage **et** `git rev-parse`/`git describe`/`git pull`),
`backend/tests/test_schedule_flow.py` (réécriture, pas juste ré-exécution),
`requirements.txt`, nouveau module `deployment.py`, nouveau module
`BobineTray`.

**Code d'installation/build** : `install.sh` (retraits Redis/workers),
`scripts/watchdog.sh` (retrait du bloc redis-server), `scripts/backup.sh`,
`scripts/restore.sh` (stratégie desktop à définir), `scripts/
migrate_unify_data_dirs.py` (instructions stales), `config.toml`,
`backend/config.toml`, nouveaux : spec PyInstaller, script `.iss` (Inno
Setup, avec `[Languages]` et règle de pare-feu), structure de paquet `.deb`
+ scripts `postinst`/`prerm`, bundle `.app`/`Info.plist`/LaunchAgent plist
macOS, `.dmg`.

**Frontend** : `frontend/src/app/settings/page.tsx` (section désinstallation/
réinitialisation/mise à jour), `frontend/src/lib/i18n.ts` (nouvelles clés
par profil, et correctif du mot « redis » dans `uninstallItemKeepPackages`),
`frontend/src/lib/usePlaybackSocket.ts` (constante calée sur le bail
primaire), `frontend/src/components/ClientLayout.tsx` (Screen Wake Lock
éventuel, Chantier C — cf. §6, portée réduite le 2026-09-06).

**Documentation projet** : `README.md`, `README.fr.md`, `docs/ARCHITECTURE.md`
(y compris le résumé d'ouverture hors sections numérotées),
`docs/cahier-des-charges-installeur.md`, `docs/cahier-des-charges-multi-os.md`,
`docs/cahier-des-charges-radio.md`, ce plan lui-même.

**Suivi release/site** : `patch.md` (racine), contenu du site bobine.fit
(liens de téléchargement, badges plateformes), notes de chaque GitHub Release
concernée.

**Contexte agents IA** : `.agents/CLAUDE.md`, `.agents/AGENTS.md`,
`.gemini/AGENTS.md`, `.gemini/state.json` (corrections immédiates
indépendantes du chantier + mises à jour liées au Lot 0 et aux Lots 1-3).

**CI/CD** : `.github/workflows/ci.yml`.

**Assets** : icône `.ico` (Windows), icône `.icns` (macOS), fichier
`.desktop` + icône menu (Linux) — à produire à partir de `Assets/Images/`.

## 9. Séquencement

1. **Lot 0**, jusqu'à validation complète (§1.4) sur l'appliance headless
   réelle, pour tout ce qui touche les fichiers qu'il modifie réellement
   (§1.1-§1.3 : `ws_manager.py`, `scheduler_manager.py`, `video_utils.py`,
   `tick_lock.py`, `import_jobs.py`, `redis_client.py`, `config.py` [champ
   `redis_url`], `main.py` [`lifespan` + `health()` + workers],
   `database.py`, `install.sh`, `scripts/watchdog.sh`, les fichiers de
   test). **Nuance après vérification croisée** : le module partagé §5.1
   (`deployment.py`, nouveau fichier) et le squelette de `BobineTray`
   (nouvelle dépendance `pystray`, nouveaux fichiers) ne recoupent aucun
   fichier de cette liste — rien n'empêche techniquement de les écrire **en
   parallèle** du Lot 0 plutôt que d'attendre sa validation complète, ce qui
   raccourcit le chemin critique d'un chantier pluri-semaines. En revanche,
   les bullets des Lots 1-3 qui éditent des fichiers **déjà touchés par le
   Lot 0** (ex. Lot 1 : correctifs de `main.py` et `config.py`) doivent,
   eux, rester strictement séquencés après la validation du Lot 0.
2. **`BobineTray`** et **module §5.1** — écrits une seule fois (peuvent
   démarrer en parallèle du Lot 0, cf. point 1), avant de dupliquer quoi
   que ce soit par OS. Pour macOS, lever d'abord l'ambiguïté `pystray` vs
   `rumps` (§4). C'est aussi dans cette étape que se pose l'abstraction
   `ProfileHandler` (backend) et la structure par profil (frontend) dans
   `settings.py`, `updates.py`, la page Réglages et `i18n.ts` — les quatre
   fichiers qui, sans cette précaution, seraient des points de collision
   garantis entre les Lots 1/2/3 (chacun y ajoutant son propre `elif`).
   Une fois cette fondation posée, ces quatre fichiers ne sont plus
   modifiés par les lots suivants — seulement complétés par de nouveaux
   fichiers, sans conflit de fusion possible.
3. **Lots 1, 2, 3** — peuvent alors avancer **réellement en parallèle**,
   y compris sur le point ci-dessus (chaque lot ajoute son propre handler/
   composant, cf. §5.1), en plus du reste de leur contenu propre à chaque
   OS (packaging, tray, mDNS, kiosque optionnel).
4. **Chantier transverse A, reste** (§5.2-§5.5) — le comportement précis de
   chaque handler de profil s'écrit au sein du lot concerné (point 3), mais
   le chantier ne peut être considéré terminé **globalement** que lorsque
   les quatre profils (headless inclus) ont été testés. La décision de
   sauvegarde/restauration (§5.5) doit être actée avant de le clore.
5. **Chantier transverse C** (§6, anti-veille hors mode kiosque) — portée
   réduite après clarification (2026-09-06), sans urgence particulière ;
   peut être traité à tout moment pendant les Lots 1-3, y compris après.
6. **Chantier transverse B** (documentation, contexte IA, `patch.md`) —
   les corrections indépendantes du chantier (§7.5, chemins
   `OpenLesmillsCinema` **dans les quatre fichiers concernés**, `STATE.md`
   manquant) peuvent être faites **immédiatement**, sans attendre quoi que
   ce soit. Le reste de la documentation se met à jour au fil de l'eau, à
   la livraison de chaque lot (voir les cases à cocher réparties dans les
   sections correspondantes).

## 10. Risques et points de vigilance

- **Faux positifs antivirus sur les `.exe` PyInstaller** — connu et
  fréquent, à documenter dans le README/site plutôt qu'à essayer de
  « corriger » (pas de solution fiable sans signature de code, hors budget
  actuel, décision #7 du CDC).
- **Capacité mono-process (Lot 0)** — validation par test de charge réel
  non négociable avant de considérer le Lot 0 terminé (§1.4).
- **Pas de cross-compilation** — chaque installeur (`.exe`, bundle macOS)
  doit être construit sur une machine du même OS ; la CI doit donc
  provisionner des runners réels par plateforme, pas seulement des
  conteneurs Linux.
- **Ne pas régresser le profil headless** — chaque branchement par profil
  (§5) doit être testé en confirmant explicitement que le chemin
  `linux-headless` reproduit exactement le comportement actuel, byte pour
  byte sur les messages utilisateur et les appels systemd.
- **Régression silencieuse de la reprise de lecture après crash** —
  décision explicite requise sur la persistance de l'état de lecture
  (§1.1, `playback_manager.py`/`radio_manager.py`) : ne pas laisser ce
  point se trancher implicitement par la simple suppression des appels
  Redis.
- **Pare-feu Windows/macOS bloquant silencieusement la télécommande
  mobile** — fonctionnalité phare du produit, à sécuriser explicitement
  par une règle de pare-feu posée à l'installation (§2, §4) plutôt que de
  découvrir le problème via des retours utilisateurs.
- **Chemins de données non inscriptibles sans élévation** — sur les trois
  nouveaux profils, si le `config.toml` par défaut n'est pas adapté
  (§2/§3/§4), la première écriture (import vidéo, base SQLite) échoue
  silencieusement dès le premier lancement. Risque critique car il
  affecte la toute première impression de l'utilisateur.
- **Mécanisme de mise à jour actuellement basé sur `git`** — sans le
  traitement complet de §5.4 (pas seulement le redémarrage final), le
  bouton « Vérifier/Appliquer une mise à jour » resterait visuellement
  actif mais cassé ou trompeur sur les trois nouveaux profils.
