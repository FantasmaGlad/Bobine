# Plan d'implémentation — Portabilité Android

Statut (2026-09-09) : **Lots 0, 2, 3, 4, 5, 6, 7 et 13 exécutés**, validés sur un **émulateur Android réel** (KVM, x86_64, API 37) avec un écran externe simulé (`overlay_display_devices`) pour le double affichage — pas seulement des builds : `app.main` (le vrai backend) démarre, sert `/kiosk` sur `127.0.0.2` et `/cinema` sur `127.0.0.1` **simultanément et indépendamment sur deux écrans distincts** (capture d'écran de l'affichage externe à l'appui, contenu confirmé réagir en direct aux réglages admin), `ForegroundService` confirmé survivre à la fermeture complète de l'app par inspection système (`dumpsys`, pas supposé), WebSocket fonctionnel, APK release signé et installé proprement. **Lot 3 partiellement clos** : le routage par hostname est validé, mais la vérification bout-en-bout de la bascule `cableOutput`/`networkOutput` était bloquée par un bug frontend préexistant et indépendant d'Android (hydratation React sur `/kiosk`) — transféré en tâche séparée (`task_67d56a94`), **résolu en cours de route** (voir Lot 4, qui a pu vérifier la bascule en direct). **Lot 13 : publication publique (GitHub Releases) volontairement différée** (décision actée). **Lot 1 largement avancé** : première installation réelle sur la tablette pilote (Xiaomi Pad 8, HyperOS/Android 16) faite dans cette session — a révélé et corrigé deux bugs invisibles sur émulateur (icône de lanceur absente ; `ERR_CLEARTEXT_NOT_PERMITTED` bloquant totalement les WebView, corrigé par un `network_security_config.xml` scopé à 127.0.0.1/127.0.0.2). Reste à faire pour clore ce lot : dock USB-C réel + écran HDMI physique (négociation DisplayPort Alt Mode/Power Delivery, et reconfirmer le scénario « écran déjà branché au démarrage à froid » du Lot 4). **Versions dynamiques posées** (pré-requis du Lot 11) : `versionCode`/`versionName` de l'APK sont désormais injectés par la CI (mêmes `display_version` Stable/Bêta que les autres plateformes), plus de constante figée. **Lot 9 (stockage) largement avancé** : `_data_root()` gère désormais Android (`getExternalFilesDir` via `BOBINE_ANDROID_DATA_DIR`, posé par `BobineForegroundService`/`bobine_bootstrap.py`) — les données utilisateur ne vivent plus dans le dossier interne où Chaquopy redéploie les sources de l'app à chaque mise à jour ; validé sur émulateur (structure complète créée avec les bonnes permissions). USB OTG probablement déjà couvert par le sélecteur système (Storage Access Framework, aucun mini-navigateur natif depuis le Lot 5) mais non testé faute de périphérique physique. **Lot 12 (déploiement) avancé** : `get_deployment_profile()`/`get_profile_handler()` gèrent désormais un profil `"android"` explicite (`AndroidHandler`), au lieu de retomber accidentellement sur `linux-desktop` — confirmé via `/api/settings` → `"deployment_profile": "android"` ; `restart_services()` non testé en conditions réelles (aucun bouton reset/restore/reset-data déclenché pour de vrai cette session). **Lot 8 (ffmpeg) : cause racine identifiée avec certitude, binaire de remplacement pas encore trouvé.** Le mécanisme de résolution de binaire et le fix de packaging natif (`useLegacyPackaging`) sont corrects et validés. Diagnostic approfondi : le blocage n'est PAS lié à un syscall exotique d'un codec, mais au **runtime de démarrage glibc lui-même** — un `busybox` statique **musl** exécuté exactement pareil (subprocess depuis l'app) fonctionne, alors que tout binaire statique **glibc** testé (peu importe la version) meurt par `SIGSYS` avant même d'atteindre `main()`. Prochaine étape nette : trouver/construire un ffmpeg statique **musl** (aucune source prête identifiée pour l'instant — BtbN et martin-riedl.de sont dynamiques, johnvansickle.com est glibc). Lot 10 non démarré ; Lot 11 reste à faire au-delà du pré-requis de versioning. Ce document est **vivant** : cocher les cases au fur et à mesure, ne jamais le laisser retomber en décalage avec la réalité du dépôt.

Ce document opérationnalise les décisions de [`docs/PortabiliteAndroid.md`](PortabiliteAndroid.md) (ci-après « le CDC ») en tâches concrètes, séquencées, découpées en lots aussi petits que possible pour qu'un agent qui reprend le travail sur un seul lot n'ait besoin de charger en contexte que ce lot-là, sans devoir relire tout le chantier.

## 0. Convention obligatoire de suivi (à respecter par tout agent travaillant sur ce plan)

**Avant de commencer un lot**, relire entièrement sa section ci-dessous, y compris les « Découvertes » déjà notées par un travail précédent — elles peuvent invalider ou nuancer les tâches prévues.

**Pendant le lot**, cocher chaque tâche `- [x]` au moment où elle est réellement terminée et vérifiée — pas en avance, pas en lot.

**En terminant un lot** (même partiellement, même bloqué), mettre à jour sa sous-section **« Découvertes »** avec, au minimum :
- **Ce qui a été fait** — concrètement, fichiers touchés, en quoi ça diffère de ce que ce plan prévoyait initialement (souvent rien ne se passe exactement comme prévu — le noter plutôt que de laisser le lecteur suivant le redécouvrir).
- **Pourquoi** ce choix précis a été fait quand plusieurs options étaient possibles.
- **Comment** valider que c'est fait (commande exacte, résultat attendu, ou constat que la validation reste à faire faute de matériel/accès).
- **Blocages** rencontrés, y compris ceux non résolus — ne jamais laisser un blocage silencieux ; l'écrire même sans solution, pour que le prochain agent ne reparte pas de zéro sur la même impasse.
- Toute **découverte qui remet en cause un autre lot** (fichier partagé, dépendance imprévue) doit aussi être répercutée dans la section du lot concerné, pas seulement ici.

Mettre également à jour la ligne **Statut** en haut de ce document à chaque lot livré, dans le même esprit que [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) et les cahiers des charges existants du dépôt.

Cette convention n'est pas optionnelle : c'est elle qui permet à un chantier pluri-lots de progresser vite malgré des agents qui n'ont, chacun, qu'une fenêtre de contexte limitée sur l'ensemble.

---

## 1. Principe d'organisation

- **Lot 0** (§2) — spike de validation des dépendances Python sous Chaquopy. **Bloquant** : go/no-go de tout le reste. À faire en tout premier, avant d'écrire une ligne de Kotlin.
- **Lot 1** (§3) — squelette du projet Android + validation matérielle de la tablette pilote. Dépend du Lot 0.
- **Lots 2 à 12** (§4-§14) — un par brique fonctionnelle, largement indépendants les uns des autres une fois les Lots 0-1 posés (voir séquencement précis, §16). Chacun touche un périmètre de fichiers distinct, listé en tête de section.
- **Lot 13** (§15) — signature, CI, publication.
- **Checklist exhaustive** (§17), **séquencement** (§16), **risques** (§18) en fin de document.

Convention de référence de fichiers : chemins relatifs à la racine du dépôt. Un fichier marqué **(nouveau)** n'existe pas encore.

---

## 2. Lot 0 — Spike de compatibilité Chaquopy (bloquant, go/no-go)

Réf. CDC §3.1. Objectif unique : lever l'incertitude sur `pydantic-core` et `psutil` avant tout investissement dans l'UI Kotlin.

### Fichiers concernés
- **(nouveau)** un projet Android Studio minimal, jetable, hors du dépôt principal ou dans un dossier `android/` séparé — à décider par l'agent qui exécute ce lot selon ce qui est le plus simple à itérer.
- `backend/requirements.txt` (lecture seule à ce stade — juste la liste des paquets à tester).

### Tâches
- [x] Créer un projet Gradle avec le plugin Chaquopy configuré — fait directement dans `android/` (pas de projet jetable séparé, fusionné avec le Lot 1 par pragmatisme). `minSdk 34`/`targetSdk 36`/`compileSdk 36` conformes au CDC §2.
- [x] Déclarer les paquets de `backend/requirements.txt` dans le bloc `chaquopy.pip` — testé d'abord tel quel (`-r requirements.txt`), puis épinglé individuellement (versions exactes de `backend/.venv` réel) une fois le problème de backtracking pip identifié (cf. Découvertes).
- [x] Synchronisation Gradle lancée, paquet par paquet, résultat noté pour chacun — voir Découvertes ci-dessous pour le détail complet (12/13 résolvent, 1 blocage sans solution — `watchdog`).
- [x] Cas `pydantic-core` échoué : évalué et tranché — downgrade `pydantic==1.10.26`/`fastapi==0.99.1` sur le profil Android uniquement (décision utilisateur), validé par un build APK complet réussi.
- [x] Cas `psutil` : **n'a en réalité pas échoué** (résout directement en version `7.1.3`) — la piste de repli `/proc/stat`/`/proc/meminfo` prévue par ce plan n'était pas nécessaire, non testée.
- [ ] Import réel de `app.main` (le vrai module du dépôt) depuis Python embarqué — **pas fait à ce stade**, explicitement déplacé au Lot 2 (cf. Découvertes : `backend/` contient `.venv/`/`data/`/`tests/` qu'il ne faut pas embarquer tel quel).
- [ ] Vérifier `sqlite3` (stdlib) sous stockage applicatif — pas encore testé.
- [ ] Vérifier `watchdog` — **impossible en l'état**, le paquet n'a aucune distribution Android (cf. Découvertes) ; à remplacer par une implémentation maison avant de pouvoir tester quoi que ce soit ici.

### Critère de sortie
- [x] **Décision écrite et actée** : Chaquopy 17.0 fait tourner `backend/requirements.txt` moyennant 4 modifications précises pour le profil Android — `pydantic`/`fastapi` downgradés en v1/0.99.1 (bloquant `pydantic-core` contourné), `pillow`/`psutil`/`zeroconf` épinglés sur une version antérieure disponible pour Android, `uvicorn` sans l'extra `[standard]` (`httptools` indisponible), `watchdog` retiré (aucune alternative trouvée à ce stade, à traiter séparément). **GO** pour la suite du chantier, confirmé par un APK complet généré avec succès.

### Découvertes

**Ce lot a été exécuté pour de vrai** (pas seulement planifié) le 2026-09-08, dans un environnement disposant déjà d'un SDK Android (platforms 36/36.1/37.0), d'un JDK 17 et d'un accès réseau — projet créé directement dans `android/` (pas de projet jetable séparé, le Lot 1 a été fusionné dans ce même travail par pragmatisme).

**1. Correction factuelle importante par rapport au CDC initial** ([`docs/PortabiliteAndroid.md`](PortabiliteAndroid.md) §3.1 citait « CPython 3.11 embarqué », avec un ton d'incertitude générale sur la maintenance de Chaquopy). En interrogeant d'abord le dépôt Maven historique de Chaquopy (`chaquo.com/maven/com/chaquo/python/gradle/`), la dernière version listée était `12.0.0` (2022-05-10) et le runtime Python le plus récent `3.8.13` — un signal fort d'abandon, potentiellement bloquant pour tout le chantier. **Ce dépôt s'est révélé être un mirroir legacy, pas la distribution actuelle.** Vérification croisée via l'API GitHub (`api.github.com/repos/chaquo/chaquopy`) : dépôt non archivé, push il y a quelques jours, dernière release **17.0.0 (2025-11-30)**. La documentation officielle courante (`chaquo.com/chaquopy/doc/current/android.html`) confirme :
- Distribution actuelle via `mavenCentral()` + `id("com.chaquo.python") version "17.0.0"` (syntaxe `plugins {}`).
- Python disponible dans Chaquopy 17.0 : **3.10, 3.11, 3.12, 3.13, 3.14** (défaut 3.10), pas seulement 3.11.
- `minSdk` ≥ 24 requis (notre décision CDC de 34 est largement au-dessus, aucun conflit).
- AGP testé : **7.3.x à 9.2.x** (les versions plus récentes « peuvent fonctionner mais n'ont pas été testées » par Chaquopy). Retenu : **AGP 9.2.1**, dernier correctif de la plage testée plutôt que la toute dernière AGP stable disponible (9.4.0 au moment de l'écriture).
- Aucun NDK à installer, bibliothèques natives Chaquopy pré-compilées.
- `buildPython` doit correspondre en majeur.mineur à la version Python de l'app. Seuls `python3.13`/`python3.14` étaient installés sur la machine utilisée → **Python retenu pour l'app : 3.13**.

**2. Piège d'outillage découvert en pratique, absent de toute doc consultée avant coup** : **AGP 9.0+ a introduit un support Kotlin intégré et REFUSE l'ancien plugin séparé** `org.jetbrains.kotlin.android` — erreur de build obtenue au premier essai (« The 'org.jetbrains.kotlin.android' plugin is no longer required for Kotlin support since AGP 9.0 »). Solution : ne déclarer AUCUN plugin Kotlin (ni dans `android/build.gradle.kts` ni dans `android/app/build.gradle.kts`), AGP tire lui-même le Kotlin Gradle Plugin 2.2.10 comme dépendance runtime. Corollaire : le bloc DSL `kotlinOptions { jvmTarget = ... }` n'existe plus non plus (`Unresolved reference 'kotlinOptions'`) — `compileOptions { sourceCompatibility/targetCompatibility }` suffit à fixer la cible JVM pour Kotlin comme pour Java sous ce nouveau mode. Piège à répercuter dans toute doc/tutoriel Android antérieur à AGP 9.0 qu'un futur agent pourrait consulter.

**3. Test réel de `chaquopy.defaultConfig.pip.install("-r", "../../backend/requirements.txt")` (fichier réel, pas retapé) — RÉSULTAT NÉGATIF, blocage confirmé** :
```
Collecting fastapi ... Using cached fastapi-0.141.1-py3-none-any.whl.metadata
Collecting sqlalchemy ... Downloading sqlalchemy-2.0.52-py3-none-any.whl.metadata
Collecting alembic ... Downloading alembic-1.19.2-py3-none-any.whl.metadata
ERROR: Could not find a version that satisfies the requirement watchdog (from versions: none)
ERROR: No matching distribution found for watchdog
```
**`watchdog`** (surveillance du dossier d'import, `backend/app/utils/watcher.py`) **n'a AUCUNE distribution disponible pour Android**, sur les deux index interrogés (PyPI public inclus, pas seulement le dépôt Chaquopy) — le CDC le classait à tort comme faible risque en se basant sur le fait qu'inotify existe dans le noyau Android ; le problème n'est pas le noyau (inotify y est bien présent, c'est le même noyau Linux) mais le fait que **le paquet PyPI `watchdog` lui-même n'a pas de wheel packagée pour la cible Android**, et le mécanisme de résolution de Chaquopy ne peut pas retomber sur une compilation depuis les sources pour une cible croisée. **Piste non testée à ce stade** : remplacer les quelques appels à `watchdog.observers` dans `watcher.py` par un petit observateur maison (`ctypes` + `inotify_init`/`inotify_add_watch` sur `libc`, ou un polling périodique plus simple mais moins réactif) — **seulement sur le profil Android**, sans toucher aux autres plateformes.

**4. Deuxième blocage découvert en isolant le reste (`watchdog` retiré temporairement de `android/app/build.gradle.kts`, packages installés un par un plutôt que via `-r`, changement de diagnostic uniquement — pas une décision finale)** :
```
ERROR: Cannot install uvicorn[standard]==0.10.9, ... uvicorn[standard]==0.52.4
because these package versions have conflicting dependencies.
The conflict is caused by:
    uvicorn[standard] 0.52.4 depends on httptools>=0.8.0; extra == "standard"
    [... répété pour TOUTES les versions d'uvicorn ...]
ERROR: ResolutionImpossible
```
**`uvicorn[standard]` échoue pour TOUTES ses versions** — la cause précise (pas une supposition, lue dans l'explication de résolution de pip) est `httptools` (parseur HTTP accéléré en C, un des extras de `[standard]`), qui n'a aucune distribution Android. **Correctif appliqué et validé en relançant le build** : installer `uvicorn` **sans** l'extra `[standard]` — `h11` (parseur HTTP pur Python, alternative de repli d'uvicorn) résolvait déjà sans problème dans le même test. Coût : pas d'accélération `uvloop`/`httptools`, acceptable pour un serveur embarqué à charge modeste (kiosque de salle, pas un service à haute concurrence) — **à documenter dans le CDC comme différence assumée entre le profil Android et les autres profils**, qui gardent `uvicorn[standard]` inchangé.

**5. Bonne nouvelle, le risque initial de ce lot est levé** : dans ce même test isolé, **`psutil`, `pillow`, `pydantic` (donc `pydantic-core`, la dépendance transitive identifiée comme le principal risque du CDC), `pystray` et `zeroconf` ont tous été acceptés par le résolveur pip sans aucune erreur** — seuls `watchdog` et l'extra `[standard]` d'`uvicorn` bloquent, pas les paquets qui inquiétaient le plus au départ.

**Décision de sortie de ce lot (provisoire, à confirmer par un build complet aboutissant à un APK installable — en cours au moment de la rédaction, résultat à ajouter ci-dessous)** : **GO conditionnel**. Chaquopy est vivant et fonctionnel pour la majorité du besoin ; deux adaptations minimes et bien identifiées sont nécessaires par rapport à `backend/requirements.txt` tel quel :
- `uvicorn[standard]` → `uvicorn` (sans extra) sur le profil Android uniquement.
- `watchdog` → à remplacer par une implémentation maison sur le profil Android uniquement (non fait à ce stade — reste un point ouvert, voir Lot 8/9 ou un nouveau lot dédié à créer si besoin).

**6. Troisième piège découvert en corrigeant les deux premiers** : une fois `watchdog` retiré et `uvicorn[standard]` remplacé par `uvicorn`, le build a tourné **47 minutes** avant d'échouer sur :
```
error: resolution-too-deep
× Dependency resolution exceeded maximum depth
╰─> Pip cannot resolve the current dependencies as the dependency graph is too complex for pip to solve efficiently.
hint: Try adding lower bounds to constrain your dependencies
```
**Ce n'est pas une incompatibilité Android** — c'est un problème mécanique de résolveur pip : `backend/requirements.txt` n'épingle **aucune** version (juste des noms de paquets nus), donc pip explore un espace combinatoire énorme (des dizaines de versions de `fastapi`/`sqlalchemy`/`alembic`/`pydantic` à croiser) avant d'abandonner. **Correctif appliqué** : épingler des versions exactes, copiées directement de `backend/.venv` réel via `python -m pip freeze` (donc des versions déjà connues pour bien fonctionner ensemble sur les autres plateformes) — pip n'a alors plus qu'à vérifier la disponibilité Android de CETTE version précise par paquet, sans recherche combinatoire. Résultat de ce build épinglé : *(à compléter — en cours au moment de la rédaction)*.

**Conséquence pour le CDC/la suite du chantier, indépendamment du résultat final** : `backend/requirements.txt` sans bornes de version n'est pas praticable tel quel pour un `pip install` croisé vers Android (même s'il l'est très bien pour l'usage normal en développement/CI desktop, où pip résout contre l'environnement natif de la machine et n'a pas cette explosion combinatoire). Le Lot 2 (ou un nouveau lot dédié) devra décider d'une stratégie durable : soit un fichier de contraintes (`constraints.txt`) dédié au profil Android dérivé de `backend/.venv`, régénéré à chaque mise à jour de `requirements.txt`, soit épingler `requirements.txt` lui-même pour toutes les plateformes (impact plus large, hors périmètre de ce chantier Android seul).

**7. Résultat du build épinglé (versions exactes copiées de `backend/.venv` réel via `pip freeze`)** : résolution quasi instantanée (15 s, contre 47 min sans épinglage) — **tout résout du premier coup** : `fastapi==0.141.1`, `uvicorn==0.52.1` (sans `[standard]`), `sqlalchemy==2.0.51`, `alembic==1.18.5`, `python-multipart==0.0.32`, `pydantic-settings==2.14.2` (donc `pydantic`/`pydantic-core` transitifs — LE risque initial de ce lot), `apscheduler==3.11.3`, `tzlocal==5.4.4`, `aiofiles==25.1.0`. Seul point : `pillow==12.3.0` (version desktop) indisponible pour Android — **seule `pillow==11.0.0` existe** sur l'index Chaquopy pour cette cible (message pip explicite : `from versions: 11.0.0`). Corrigé en épinglant `pillow==11.0.0` pour le profil Android (API stable entre ces versions pour l'usage de Bobine — vignettes/redimensionnement, pas de fonctionnalité récente utilisée). `psutil==7.2.2`, `pystray==0.19.5`, `zeroconf==0.151.3` retestés dans la même passe épinglée — résultat à ajouter avec le build final.

**8. Deux derniers ajustements de version, mêmes symptômes que Pillow — un correctif par itération, chacun confirmé en ~15-20 s grâce à l'épinglage (§7)** :
- `psutil==7.2.2` (desktop) indisponible → **seule `psutil==7.1.3` existe pour Android**, retenue. C'est le paquet identifié comme risque n°1 dans le CDC initial (extension C, pas de support Android officiel documenté en amont) — **la crainte ne s'est pas concrétisée : psutil a bien un wheel Android**, juste sur un patch antérieur.
- `zeroconf==0.151.3` (desktop) indisponible → la version Android la plus récente disponible est **`0.39.4`**, un écart plus large que pour pillow/psutil (desktop est ~110 versions mineures plus loin). Retenue pour l'instant faute d'alternative ; **point de vigilance pour un lot ultérieur** (Lot 7, mDNS) : vérifier que l'API utilisée par `backend/app/utils/mdns.py` (probablement `Zeroconf`, `ServiceInfo`, `register_service`) est bien compatible avec cette version plus ancienne — pas vérifié à ce stade, seule la résolution pip a été testée, pas le comportement runtime.

**9. CORRECTIF DU POINT 8 CI-DESSUS — le risque initial de ce lot n'était PAS levé, fausse alerte positive.** En relançant le build complet avec tout épinglé (§7-8), l'étape suivante a échoué sur `fastapi` avec un message pip explicite : *« some packages in these conflicts have no matching distributions available for your environment: pydantic-core »*. Ce n'est PAS le même schéma que pillow/psutil/zeroconf (une version antérieure existe) — **aucune version fonctionnelle de `pydantic-core` n'existe pour Android.**

**Diagnostic isolé (`chaquopy.pip.install("pydantic-core")` seul, sans contrainte de version, pour lire précisément ce que pip trouve)** — résultat alarmant et déterminant :
```
Collecting pydantic-core
  Downloading pydantic_core-0.0.1-py3-none-any.whl.metadata (637 bytes)
Successfully installed pydantic-core-0.0.1
```
`pip` **« réussit »** silencieusement à installer `pydantic-core`, mais la version retenue (`0.0.1`) n'est PAS la vraie librairie. Vérification sur PyPI (`pypi.org/pypi/pydantic-core/0.0.1/json`) : c'est un **paquet placeholder vide, publié en 2022 par l'auteur de Pydantic, description littérale « Placeholder until pydantic-core is released »**, sans aucun code fonctionnel (`requires_dist: None`). La raison technique : c'est le **seul** wheel jamais publié sous ce nom au format `py3-none-any` (indépendant de plateforme) — toutes les vraies versions (2.x, l'extension Rust compilée que Pydantic v2/FastAPI utilisent réellement) sont taguées par plateforme (Linux/macOS/Windows) et **invisibles** pour la résolution croisée Android de Chaquopy. Le résolveur pip, ne voyant aucune version « éligible » parmi les vraies, se rabat sans avertir sur ce fantôme de 2022.

**Conséquence directe, à ne pas minimiser** : **FastAPI et Pydantic v2, tels qu'utilisés aujourd'hui par tout `backend/app/`, ne peuvent PAS tourner sous Chaquopy sur Android en l'état.** C'est un point d'arrêt réel pour la prémisse centrale du CDC (« réutiliser le même backend FastAPI sans le réécrire »), pas un simple ajustement de version comme les trois précédents. `pydantic-core`/`pydantic-settings`/`fastapi` ont été retirés de la configuration `android/app/build.gradle.kts` en attendant un arbitrage — voir le CDC pour les options possibles et la demande de décision à l'utilisateur.

**10. Décision utilisateur actée + confirmation finale par build réel : downgrade Pydantic v1 sur le profil Android uniquement.** Testé directement (pas seulement discuté) : `pydantic<2` → résout en `pydantic-1.10.26-py3-none-any.whl` (vraie librairie pure Python, pas un placeholder), combiné avec `fastapi<0.100.0` → résout en `fastapi-0.99.1` (dernière version encore compatible Pydantic v1, avec `starlette-0.27.0`/`anyio-4.15.1`). **Build complet réussi, APK généré** (`android/app/build/outputs/apk/debug/app-debug.apk`) avec toute la stack pinée à ces versions exactes. Configuration finale conservée dans `android/app/build.gradle.kts`.

**Périmètre de compatibilité Pydantic v1 à traiter dans `backend/app/` pour le profil Android** (mesuré par grep sur tout le backend, pas estimé — volontairement petit, pas une réécriture) :
- [`backend/app/config.py:6`](../backend/app/config.py) — `from pydantic_settings import BaseSettings` → `pydantic.BaseSettings` (intégré nativement à Pydantic v1, pas besoin du paquet séparé `pydantic-settings`, lui-même indisponible puisqu'il exige Pydantic v2).
- [`backend/app/routers/radio_announcements.py:20,75`](../backend/app/routers/radio_announcements.py) — `field_validator` (syntaxe v2) → `validator` (syntaxe v1).
- [`backend/app/routers/settings.py:339`](../backend/app/routers/settings.py) — `payload.model_dump(exclude_unset=True)` → `payload.dict(exclude_unset=True)`.
- Tout le reste des ~15 fichiers qui importent Pydantic dans `backend/app/` n'utilise que `BaseModel` nu, syntaxe identique entre v1 et v2 — pas de changement necessaire.
- **Non fait à ce stade** (Lot 0 ne teste que la résolution des dépendances, pas encore l'import du vrai `backend/app/` — cf. Lot 2) : écrire la couche de compatibilité réelle. Vu le périmètre mesuré ci-dessus, l'option la plus simple est probablement un petit module `backend/app/_compat_pydantic_v1.py` (ou équivalent) qui n'est importé que sur le profil Android, plutôt que de parsemer le code de branches conditionnelles — à trancher au Lot 2.
- **Maintenance à long terme, à garder à l'esprit pour tout futur agent** : le profil Android reste figé sur FastAPI 0.99.1/Pydantic v1 (millésime mi-2023) tant que `pydantic-core` n'a pas de distribution Android — toute nouvelle route/schéma Pydantic ajoutée au backend doit rester compatible avec les deux syntaxes (ou passer par la couche de compatibilité ci-dessus), indéfiniment.

**Bilan complet et final du Lot 0 — GO confirmé** : sur les 13 paquets de `requirements.txt` (hors `pyobjc-*`), **12 résolvent** (dont 3 avec un pin Android différent du desktop — pillow 11.0.0, psutil 7.1.3, zeroconf 0.39.4 — et `uvicorn` sans l'extra `[standard]`, `httptools` indisponible), **1 seul reste un blocage sans solution trouvée à ce stade** (`watchdog`, cf. pistes proposées plus haut — à traiter dans un lot dédié). Le blocage initial sur `pydantic-core` (bloquant dur, pas un simple ajustement de version) est levé par le downgrade Pydantic v1 côté Android, décision actée et validée par un vrai build APK réussi. Chaquopy 17.0 est vivant, activement maintenu, et fonctionnel pour l'essentiel du besoin de Bobine. **Le chantier peut avancer vers le Lot 1 (déjà largement entamé en pratique dans ce même travail) et le Lot 2.**

---

## 3. Lot 1 — Squelette du projet Android + validation matérielle

Dépend du Lot 0 (le squelette réutilise sa configuration Chaquopy validée). Réf. CDC §6.

### Fichiers concernés
- **(nouveau)** structure définitive du projet Android (remplace le projet jetable du Lot 0 si celui-ci était hors dépôt), à un emplacement à trancher : `android/` à la racine, en miroir de `backend/`, `frontend/`, `assistant/`.
- **(nouveau)** `android/app/build.gradle.kts`, `android/settings.gradle.kts`, manifeste `AndroidManifest.xml`.

### Tâches
- [ ] Créer la structure de projet définitive, avec la configuration Chaquopy validée au Lot 0.
- [ ] `minSdk`/`targetSdk`/`compileSdk` conformes à la décision du CDC §2, testés contre Android 16 réel sur la tablette pilote.
- [ ] Une `Activity` minimale qui démarre le `ForegroundService` (squelette vide à ce stade, complété au Lot 6) et affiche juste un texte de statut — pas encore de WebView.
- [ ] Sur la tablette pilote (Xiaomi Pad 8), avec le dock USB-C réellement utilisé : vérifier la négociation DisplayPort Alt Mode (brancher un écran/vidéoprojecteur HDMI et confirmer qu'Android détecte un second `Display` via `DisplayManager.getDisplays()` — un simple log suffit à ce stade, pas encore de `Presentation`).
- [ ] Vérifier que le dock alimente correctement la tablette en Power Delivery pendant la sortie vidéo active (pas de décharge progressive de la batterie).

### Critère de sortie
- [x] APK installable sur la tablette pilote, backend Python démarré (santé vérifiable via `adb logcat` ou un endpoint `/api/health` accessible depuis un navigateur du même réseau) — **partiel**, voir Découvertes : pas encore testé avec le dock/HDMI réel (second écran détecté par `DisplayManager`), ni la négociation Power Delivery.

### Découvertes

**Première installation réelle sur la tablette pilote (Xiaomi Pad 8, HyperOS/Android 16, `adb` USB) dans cette session — deux bugs réels révélés qu'aucun test sur émulateur (API 37, x86_64) n'avait fait apparaître jusqu'ici :**

1. **Icône de lanceur absente** — `AndroidManifest.xml` ne déclarait `android:icon` nulle part et aucune ressource `mipmap` n'existait (`android/app/src/main/res/` ne contenait que `values/` et un `mipmap-anydpi-v26/` vide) : un oubli du Lot 1 initial, invisible sur émulateur si on ne regarde jamais l'écran d'accueil. Corrigé par une icône adaptive standard (`mipmap-anydpi-v26/ic_launcher.xml` + `ic_launcher_round.xml`, fond `@color/ic_launcher_background` = `#F8F9FA` réutilisé de `assistant/src-tauri/tauri.conf.json` pour la cohérence inter-plateformes, premier plan généré par script à partir de `packaging/linux/icons/hicolor/512x512/apps/bobine.png`, réduit à 60% et centré pour respecter la zone de sécurité de 66% des icônes adaptive — sinon rogné selon la forme de masque du launcher). `minSdk` étant 34 (> 26), aucune ressource `mipmap` plate/legacy par densité n'est nécessaire, seule la variante adaptive suffit. Vérifié visuellement sur l'écran d'accueil HyperOS après désinstallation/réinstallation propre (le simple `adb install -r` ne suffisait pas à rafraîchir l'icône déjà mise en cache par le launcher MIUI).
2. **`net::ERR_CLEARTEXT_NOT_PERMITTED` dans les deux WebView (MainActivity et BobinePresentation)** — bloquant, l'app ne pouvait plus afficher `/kiosk` ni `/cinema` du tout sur ce vrai matériel, alors que ce même APK fonctionnait sans ce problème sur l'émulateur (WebView système différent, 151.x sur le Xiaomi vs. build AOSP sur l'émulateur). Depuis API 28, Android bloque par défaut tout trafic HTTP en clair — corrigé en ajoutant `android/app/src/main/res/xml/network_security_config.xml` (référencé via `android:networkSecurityConfig` dans le Manifest) autorisant explicitement le clair **uniquement** vers `127.0.0.1` et `127.0.0.2` — les deux seuls hostnames que l'architecture utilise réellement (cf. CDC §4, décision Lot 3) — plutôt qu'un `usesCleartextTraffic="true"` global qui aurait ouvert le clair vers n'importe quel domaine. Confirmé résolu : le WebSocket `/ws/playback` se connecte, `/kiosk` s'affiche (logo, horloge, « EN ATTENTE DU PROCHAIN COURS »), capture d'écran à l'appui.
3. **Friction d'installation via `adb`** (pas un bug Bobine, mais à savoir pour tout futur agent/testeur) : `adb install` échouait avec `INSTALL_FAILED_USER_RESTRICTED` tant que Paramètres → Options pour développeurs → « Installation via USB » n'est pas explicitement activé côté HyperOS — un simple `adb install -r` par-dessus une version déjà installée ne suffit pas non plus à rafraîchir l'icône du launcher, une désinstallation puis réinstallation propre (`adb uninstall` + `adb install` sans `-r`) a été nécessaire.
4. **Non résolu, hors périmètre de ce lot** : en testant la découverte mDNS (Lot 7) avec cette même tablette sur le vrai Wi-Fi domestique, `bobine.local` se résout correctement en `192.168.1.60` depuis la machine de développement (mDNS fonctionne), mais la connexion TCP vers le port 8000 est ensuite silencieusement filtrée (`nmap -Pn -p8000` → `filtered`, alors que le backend répond bien en local et via sa propre IP LAN depuis l'appareil lui-même) — probablement un pare-feu HyperOS (app Sécurité) ou une isolation client sur le routeur Wi-Fi, pas un bug Android/Bobine. À investiguer côté réglages tablette/routeur, pas côté code, avant de conclure quoi que ce soit sur le Lot 7.
5. `platform.system()` sous Chaquopy renvoie bien `"Android"` sur ce vrai matériel aussi (pas seulement sur l'émulateur) — confirme la découverte du Lot 7 de façon indépendante.
6. **Le bug d'hydratation React** (`task_67d56a94`, mentionné aux Lots 3/4) **se reproduit identiquement sur ce vrai matériel** (`Uncaught Error: Minified React error #418` dans `WebViewConsole`) mais reste **non bloquant** : la page `/kiosk` s'affiche et fonctionne visuellement malgré l'erreur logguée (React récupère silencieusement de l'écart d'hydratation) — cohérent avec ce qui avait été observé sur émulateur, confirme que ce n'est pas un problème spécifique au matériel réel.

Reste à faire pour clore formellement ce lot : brancher le dock USB-C réel avec un écran/vidéoprojecteur HDMI et confirmer la détection `DisplayManager`/négociation Power Delivery (aucun dock disponible au moment de cette session) — dépend aussi du Lot 4 pour repasser sur le cas cold-boot-avec-écran-déjà-branché en conditions réelles.

---

## 4. Lot 2 — Frontend statique embarqué

Réf. CDC §1. Indépendant des Lots 0-1 sur le fond (peut être préparé en parallèle), mais son intégration finale dans l'APK dépend du Lot 1.

### Fichiers concernés
- `frontend/` (aucune modification de code attendue — l'export statique existe déjà via `next.config.ts` → `output: "export"`).
- **(nouveau)** tâche Gradle ou script qui copie `frontend/out/` (après `npm run build`) vers les assets Android (`android/app/src/main/assets/www/` ou équivalent).
- **(nouveau)** `.github/workflows/` — étape de build frontend à ajouter au pipeline Android (coordination avec le Lot 13).

### Tâches
- [x] Vérifié : `npm run build` produit un `frontend/out/` fonctionnel (21 routes statiques générées), aucun changement nécessaire côté frontend.
- [x] Tâche Gradle `stagePythonSources` (+ `buildFrontendStatic`) écrite dans `android/app/build.gradle.kts`, déclenchée avant `mergeDebugPythonSources`/`mergeReleasePythonSources` (voir Découvertes pour le piège de validation Gradle rencontré).
- [x] Backend confirmé servant ces fichiers **avec une modification** (pas zéro comme prévu — voir Découvertes) : une branche Android dédiée dans `main.py`, pas juste un chemin de recherche différent en config.

### Critère de sortie
- [x] **Confirmé sur émulateur réel** (pas seulement en théorie) : `http://127.0.0.1:8000/kiosk/` répond `200 OK` avec le vrai HTML Next.js, et la WebView affiche effectivement l'écran d'attente Bobine (logo, horloge, « EN ATTENTE DU PROCHAIN COURS ») — capture d'écran validée visuellement pendant ce lot.

### Découvertes

**Ce lot a été exécuté avec un vrai émulateur Android, pas seulement un build.** L'environnement dispose d'un SDK Android complet avec accélération KVM et un AVD déjà configuré (`Medium_Phone`, x86_64, API 37, image Google Play) — après un premier souci d'autorisation ADB (état `unauthorized` persistant, résolu par `-wipe-data` au redémarrage de l'émulateur, probablement une clé adb enregistrée après la création initiale des données utilisateur de l'AVD), l'émulateur a servi de banc de test réel pour tout ce lot : install APK (`adb install`), lancement (`adb shell am start`), inspection des logs Python (`adb logcat`, tag `python.stderr`/`python.stdout`), et capture d'écran (`adb shell screencap`) pour valider visuellement le rendu WebView — pas seulement une réponse HTTP.

**1. Piège Gradle : dépendance implicite non déclarée.** La première version de la tâche `stagePythonSources` (hookée seulement sur `preBuild`) a fait échouer `mergeDebugPythonSources` avec *"Property has implicit dependency"* — la validation stricte de Gradle 9 exige une dépendance EXPLICITE entre la tâche qui lit un répertoire généré et celle qui l'écrit ; un ordre d'exécution correct via un chemin de dépendance transitif (via `preBuild`) ne suffit pas. Corrigé en ajoutant `tasks.matching { it.name.startsWith("merge") && it.name.endsWith("PythonSources") }.configureEach { dependsOn(stagePythonSources) }`, générique sur toutes les variantes (debug/release).

**2. Oubli concret détecté seulement à l'exécution réelle : `uvicorn` avait disparu de `chaquopy.pip`.** En restaurant la liste complète des paquets après le diagnostic isolé de `pydantic-core` (Lot 0), `uvicorn` a été omis par erreur — un simple `grep`/relecture du fichier ne l'aurait pas forcément fait remarquer, mais lancer l'app réellement sur l'émulateur a immédiatement produit `ModuleNotFoundError: No module named 'uvicorn'` dans `adb logcat`. **Preuve concrète que tester sur un vrai appareil/émulateur trouve des classes d'erreurs qu'une relecture de configuration ne trouve pas.** Corrigé : `install("uvicorn==0.52.1")` réajouté.

**3. `zoneinfo` (stdlib) ne trouve pas la base de données de fuseaux horaires sur Android** — `ZoneInfoNotFoundError: 'No time zone found with key Europe/Paris'`, levée par `tzlocal` (utilisé par `scheduler_manager.py`) via le module stdlib `zoneinfo`. Contrairement aux distributions Linux desktop, Android n'a pas de `/usr/share/zoneinfo` à l'emplacement attendu par CPython. **Corrigé en ajoutant `install("tzdata")`** (le paquet PyPI qui embarque la base IANA) à la configuration Chaquopy — absent de `backend/requirements.txt` car inutile ailleurs (toutes les autres plateformes ont une base système).

**4. Le périmètre de compatibilité Pydantic v1 mesuré au Lot 0 était SOUS-ESTIMÉ — corrigé ici avec un grep plus complet.** Le premier grep (Lot 0) cherchait `model_config|ConfigDict|field_validator|model_validate|model_dump|BaseSettings` et concluait à 3 points isolés. Exécuter réellement `app.main` sur l'émulateur a révélé, un crash à la fois puis confirmé par un grep élargi (`computed_field|model_fields|model_fields_set|from_attributes|...`), une liste **bien plus longue** :
- **`from_attributes = True` dans 14 `class Config` à travers 6 fichiers** (`videos.py`, `audio_playlists.py`×4, `playlists.py`×4, `backgrounds.py`, `audio.py`×3, `logs.py`) — le nom v2 de l'ancien `orm_mode` (v1). Sans ce dernier, la construction des modèles de réponse à partir d'objets SQLAlchemy (`response_model=...`) échoue silencieusement en v1. **Corrigé en ajoutant `orm_mode = True` à côté de `from_attributes = True` dans chacun** (vérifié empiriquement : Pydantic v2 accepte `orm_mode` comme alias legacy de `from_attributes`, avec un simple avertissement de dépréciation, pas une erreur — donc les deux clés cohabitent sans risque sur les deux versions).
- **`settings.model_fields`** (`config.py:312`, itération sur les noms de champs) → repli `settings.__fields__` (v1, sémantique identique pour un usage en boucle `for`).
- **`payload.model_fields_set`** (`radio.py:227`, `radio_announcements.py:191`) → repli `payload.__fields_set__` (v1, sémantique identique).
- **`computed_field`** (`backgrounds.py`, propriété calculée `is_image` incluse dans la sérialisation JSON) — **le seul cas sans équivalent direct en v1** : une simple `@property` n'est PAS incluse dans `.dict()` par Pydantic v1. Résolu par un petit module partagé **`backend/app/utils/_pydantic_compat.py`** : `computed_field` devient un no-op sur v1 (garde la propriété normale) combiné à un mixin `_ComputedFieldsCompatMixin` qui surcharge `.dict()` pour y injecter les propriétés marquées — vide/sans effet sur v2 (Pydantic v2 gère déjà tout ça nativement). Vérifié : `is_image` apparaît bien dans `model_dump()` côté desktop (v2) après ce changement, comportement inchangé.
- Tous ces correctifs suivent le même schéma `try: <v2> except ImportError: <v1>` (ou `getattr(obj, "v2_name", None) or obj.v1_name`) déjà utilisé au Lot 0 — **zéro fichier dupliqué entre profils**, un seul `backend/app/` partagé. Suite complète des tests desktop (32/32) revérifiée après chaque changement — aucune régression, seulement des avertissements de dépréciation déjà présents ou nouvellement ajoutés (`orm_mode`), jamais des erreurs.
- **Le message du CDC (« 3 points, périmètre petit ») était donc correct dans l'esprit (le vrai code métier n'a pas eu besoin d'être réécrit) mais incomplet dans le compte exact** — corrigé dans le CDC (§3.1) avec le décompte réel.

**5. `watchdog` : le repli par polling (`app/utils/_polling_observer.py`, écrit au Lot 0 sur la seule base de la lecture du code) fonctionne réellement** — confirmé par les logs `adb logcat` : `"Watcher : Initialisation sur /data/data/com.bobine.app/files/.../data/watched"` pour les 4 dossiers surveillés, sans erreur, `app.main` a démarré normalement avec ce repli actif.

**6. Le placement de `frontend/out` n'est PAS un simple ajustement de chemin de configuration — Chaquopy impose une structure d'assets fixe qui casse l'hypothèse initiale de ce lot ("le code Python ne doit pas être modifié").** Contrairement à l'attente initiale, Chaquopy monte le contenu de `chaquopy.sourceSets` sous un dossier **fixe** `AssetFinder/app/<contenu du srcDir>` sur l'appareil — `AssetFinder/app/` n'est pas configurable ni renommable depuis `chaquopy.sourceSets`, ce n'est pas une simple projection du nom du dossier choisi côté Gradle (`backend`). La logique existante de `main.py` (3 `.parent` pour retomber sur un `frontend/out` sibling de `backend/`) suppose implicitement une hiérarchie de dossiers réelle qui n'existe pas sous cette structure fixée par Chaquopy — **premier test réel : `404 Not Found` sur `/kiosk/`, log `"Dossier frontend/out introuvable"`**, confirmant le problème. Résolu par une branche Android explicite dans `main.py`, détectée via `hasattr(sys, "getandroidapilevel")` (attribut du build CPython officiel pour Android, présent uniquement sous Chaquopy — moyen fiable et standard, pas une supposition) : sur ce profil, `frontend_out` est placé comme sibling du paquet `app/` (2 `.parent`, pas 3), et la tâche Gradle copie `frontend/out/` vers `pyStage/backend/frontend_out/` en conséquence. **Correction au CDC** : l'objectif « le code Python de service des statics ne doit pas être modifié » n'est donc pas entièrement tenu — un petit ajout ciblé (une branche supplémentaire dans un `if/elif` déjà présent pour Windows/macOS/Linux) était nécessaire, cohérent avec le style déjà en place dans ce fichier.

**7. La `WebView` peut se connecter AVANT que le serveur écoute réellement.** `bobine_bootstrap.start_server_once()` démarre uvicorn dans un thread Python et rend la main immédiatement — `MainActivity` chargeait l'URL sans attendre, produisant `net::ERR_CONNECTION_REFUSED` (constaté par capture d'écran réelle de la WebView, pas juste un test `curl`). Corrigé par un `WebViewClient.onReceivedError` qui recharge l'URL après 500 ms sur toute erreur de la frame principale — solution intérimaire pour ce lot, **à remplacer par une vraie coordination avec le cycle de vie du `ForegroundService`** au Lot 6 (le service saura quand uvicorn est réellement prêt, plutôt qu'un réessai à l'aveugle).

**Validation finale** : capture d'écran réelle de la `WebView` sur l'émulateur confirmant le rendu correct de l'écran d'attente `/kiosk` (logo Bobine, horloge, « EN ATTENTE DU PROCHAIN COURS ») — comportement identique à ce que décrit `docs/ARCHITECTURE.md` §4 pour une bibliothèque vide. **Lot 2 : GO, terminé.**

---

## 5. Lot 3 — Résolution du routage hostname (`/kiosk` vs `/cinema`)

Réf. CDC §4 — **décision à trancher avant le Lot 4**, qui en dépend directement.

### Fichiers concernés
- [`frontend/src/lib/useDisplayOutputRedirect.ts`](../frontend/src/lib/useDisplayOutputRedirect.ts) — modification potentielle si la décision retenue nécessite une troisième catégorie de hostname (au-delà de « câblé »/« réseau »).
- **(nouveau)** code Kotlin décidant quelle URL charge quelle `WebView`/`Presentation`.

### Tâches
- [x] Tranché — **ni `bobine.local` (mDNS) ni l'IP LAN de la tablette : `127.0.0.2`** (voir Découvertes pour le raisonnement et la validation empirique). Solution plus simple que les deux options envisagées initialement par ce plan, sans dépendance au Lot 8 ni à l'état du Wi-Fi.
- [x] `isWiredDisplay()` gère déjà correctement ce cas **sans aucune modification** : la comparaison est une égalité stricte de chaîne (`"127.0.0.1"`/`"localhost"`), donc `"127.0.0.2"` est automatiquement classé « réseau ». `useDisplayOutputRedirect.ts` n'a pas été touché.
- [x] `android/app/src/main/java/com/bobine/app/MainActivity.kt` mis à jour : la `WebView` tactile charge désormais `http://127.0.0.2:8000/kiosk/` au lieu de `127.0.0.1`.
- [~] Test du basculement `cableOutput` réalisé partiellement — voir Découvertes : bloqué par un bug non lié à Android, transféré en tâche séparée.

### Critère de sortie
- [~] Le mécanisme de routage par hostname (`127.0.0.1` = câblé, `127.0.0.2` = réseau, tous deux atteignant le même serveur) est validé empiriquement. La vérification complète du comportement de bascule `cableOutput`/`networkOutput` en conditions réelles reste bloquée par un bug frontend préexistant, indépendant de ce chantier (voir Découvertes) — à reprendre une fois ce bug corrigé.

### Découvertes

**1. Décision retenue : `127.0.0.2` plutôt que `bobine.local` ou l'IP LAN.** Les deux options envisagées par ce plan avaient chacune un coût : `bobine.local` dépend de la résolution mDNS depuis l'appareil lui-même vers son propre service (Lot 8, pas encore fait, et une résolution mDNS en boucle locale a des cas limites connus sur certains Android) ; l'IP LAN de la tablette dépend de l'état Wi-Fi (absente/instable avant association, ou si la tablette est un jour reliée en filaire uniquement). **Constat exploité** : le bloc entier `127.0.0.0/8` est loopback, pas seulement `127.0.0.1` — n'importe quelle adresse de ce bloc atteint le même serveur local. Vérifié en pratique sur l'émulateur avant toute décision :
```
adb shell "echo -e 'GET /api/health HTTP/1.0\r\n\r\n' | nc 127.0.0.2 8000"
→ HTTP/1.1 200 OK ... {"status":"ok",...}
```
`isWiredDisplay()` (comparaison de chaîne stricte) classe `127.0.0.2` comme « réseau » sans aucune modification de code frontend. Confirmé ensuite dans la vraie `WebView` de l'app (pas seulement via `nc`) : `http://127.0.0.2:8000/kiosk/` s'affiche correctement, sans erreur `ERR_CLEARTEXT_NOT_PERMITTED` ni configuration de sécurité réseau Android supplémentaire (capture d'écran validée). **Zéro dépendance au Lot 8, zéro dépendance à l'état Wi-Fi** — plus simple et plus robuste que les deux pistes envisagées initialement.

**2. Bug découvert en tentant de valider la bascule `cableOutput`, non lié à Android — transféré en tâche séparée, PAS corrigé ici.** En essayant de vérifier que la `WebView` sur `127.0.0.1` suit bien `cableOutput` (bascule via `PUT /api/settings/display-output`), la page a levé une erreur JS (`Uncaught Error: Minified React error #418` — erreur d'hydratation React) systématiquement lors du chargement de `/kiosk/` depuis l'export statique de production. **Reproduit indépendamment sur un vrai Chrome desktop** (même export statique, backend local sur le port 8002) — donc **pas un problème de portage Android**, un bug frontend préexistant qui affecte potentiellement aussi les profils desktop/appliance en production. N'apparaît pas sous `next dev`. Cause exacte non identifiée (probablement un rendu dépendant de l'heure/date dans l'écran d'attente, à confirmer) — hors périmètre de ce lot, transféré à une session dédiée plutôt que d'être creusé ici au risque de dériver du chantier Android. **Ce bug empêche de conclure définitivement sur le comportement de `useDisplayOutputRedirect`** dans ce lot : le mécanisme de routage par hostname lui-même (le sujet réel du Lot 3) est validé, mais la vérification bout-en-bout de la bascule kiosk/cinéma devra être refaite une fois ce bug corrigé.

**3. Découverte fonctionnelle majeure, incidente à ce lot mais critique : les WebSockets ne fonctionnaient pas du tout sur Android avant ce lot.** En diagnostiquant le problème de bascule ci-dessus, les logs ont révélé `"GET /ws/playback HTTP/1.1" 404 Not Found` avec `"No supported WebSocket library detected. Please use 'pip install uvicorn[standard]'"`. Conséquence directe, non anticipée, du retrait de l'extra `[standard]` d'uvicorn au Lot 0 (motivé par `httptools`, indisponible sur Android) — **l'extra `[standard]` regroupe aussi le support WebSocket**, pas seulement l'accélération HTTP comme supposé initialement. `/ws/playback` est le mécanisme central de synchronisation temps réel de Bobine (état de lecture, `useDisplayOutputRedirect` en dépend lui-même via `usePlaybackSocket`) — sans lui, une bonne partie de l'admin et des écrans clients ne fonctionne pas du tout, pas juste plus lentement. **Corrigé** : ajout de `install("websockets")` (résout proprement pour Android, testé) dans `android/app/build.gradle.kts`, sans reprendre `httptools`/`uvloop`. Validé par un vrai test de connexion WebSocket : `wsproto`/`websockets` côté client Python a reçu l'événement `boot_id` attendu du protocole. **Le §3.1 du CDC concernant le compromis `uvicorn` sans `[standard]` doit être complété avec ce point** — corrigé dans le CDC en même temps que ce lot.

**4. `MainActivity.kt` instrumentée pour le débogage** (`WebView.setWebContentsDebuggingEnabled(true)` + `WebChromeClient.onConsoleMessage` redirigé vers `Log.d("WebViewConsole", ...)`) — c'est ce qui a permis de repérer le bug d'hydratation (§2) au lieu de rester bloqué sans visibilité sur les erreurs JS. À conserver pour les lots suivants (utile dès le Lot 4/5 pour déboguer la `Presentation` et le WebView shell).

---

## 6. Lot 4 — Double affichage (`DisplayManager` + `Presentation`)

Dépend des Lots 1 (détection du second écran déjà validée) et 3 (URL à charger tranchée). Réf. CDC §3.2.

### Fichiers concernés
- **(nouveau)** classe Kotlin héritant de `android.app.Presentation`, gérée par le `ForegroundService` (Lot 6) plutôt que par l'`Activity` (pour survivre à la fermeture de l'app, cf. Lot 6).
- **(nouveau)** `DisplayManager.DisplayListener` pour réagir au branchement/débranchement du dock en cours d'exécution, pas seulement au démarrage.

### Tâches
- [x] `BobinePresentation.kt` implémentée — charge `http://127.0.0.1:8000/cinema/` dans une `WebView` plein écran sur le `Display` externe, gérée par `BobineForegroundService` (Lot 6, écrit en même temps — voir sa section pour le détail).
- [x] Cycle de vie géré via `DisplayManager.DisplayListener` (`onDisplayAdded`/`onDisplayRemoved`) — testé réellement en simulant un branchement/débranchement à chaud (voir Découvertes).
- [x] Repli si aucun écran externe : aucune action — la tablette continue d'afficher `/kiosk` normalement, pas de bascule automatique (le plus simple, cohérent avec « la tablette doit rester utilisable pour autre chose »).
- [ ] Décodage matériel H.264/HEVC réel : **non testé** — nécessite la tablette pilote (l'émulateur x86_64 n'a pas de décodeur vidéo matériel représentatif) et un vrai fichier vidéo importé, reste à faire au Lot 1 (validation matérielle).

### Critère de sortie
- [x] **Validé sur émulateur, pas sur la tablette pilote** (dock/vidéoprojecteur réels restent à faire) : `/kiosk` sur l'écran tactile et `/cinema` sur l'écran externe simultanément, chacun suivant son propre réglage (`isWiredDisplay()`/`useDisplayOutputRedirect`) de façon indépendante — confirmé par capture d'écran de l'affichage externe montrant le contenu réel (`/cinema` vide → « Aucun cours disponible pour le moment. »), et confirmé que basculer `cableOutput` vers `cinema` depuis l'admin met à jour le contenu de l'écran externe **en direct** (push WebSocket, pas de rechargement) sans affecter l'écran tactile.

### Découvertes

**Ce lot, le Lot 5 et le Lot 6 ont été implémentés ensemble dès le départ** — le plan prévoyait initialement de prototyper la `Presentation` dans l'Activity puis de la faire migrer vers le `ForegroundService` au Lot 6 ; ça a semblé une perte de temps évidente une fois l'architecture comprise, donc `BobineForegroundService` a été écrit directement comme propriétaire de la `Presentation`, sans étape intermédiaire dans `MainActivity`. Voir la section Lot 6 pour le détail de cette classe.

**Bug réel trouvé et corrigé par le test, pas par la lecture du code : `Presentation.show()` peut échouer avec `WindowManager.InvalidDisplayException` (« the specified display can not be found ») même quand le `Display` apparaît bien dans `DisplayManager.getDisplays()`.** Deux scénarios testés séparément sur l'émulateur (écran externe simulé via `adb shell settings put global overlay_display_devices`), avec des résultats très différents :
- **Écran déjà présent AVANT le démarrage à froid de l'app** (`am force-stop` puis relance avec l'écran simulé déjà actif) : `Presentation.show()` échoue de façon **systématique et reproductible** sur la toute première tentative, et un réessai simple (même référence `Display`, dans le même process) échoue **encore après 15 tentatives espacées de 500ms (~8,7s au total)** — testé explicitement, pas supposé.
- **Écran branché PENDANT que l'app tourne déjà** (app démarrée sans écran externe, puis `overlay_display_devices` activé après coup — le scénario réel d'un dock HDMI qu'on branche sur une tablette déjà allumée) : `Presentation.show()` réussit **du premier coup, sans aucun réessai**, à chaque fois.
- **Conclusion retenue** : ce n'est probablement pas un bug de la logique Kotlin elle-même, mais une particularité du processus tout juste démarré (« cold start ») — la connexion binder du process à `WindowManagerService` ne semble pas encore prête à ce moment précis pour un écran déjà listé, alors qu'un évènement `onDisplayAdded` reçu par un process déjà « chaud » fonctionne immédiatement. **Le scénario qui compte le plus en usage réel (brancher le dock sur une tablette déjà allumée) est donc validé sans réserve** ; le scénario plus rare (tablette redémarrée alors que le dock est déjà branché) reste un point de vigilance à revérifier sur la tablette pilote réelle — l'émulateur logiciel n'est peut-être pas représentatif du vrai timing matériel sur ce point précis.
- **Correctif retenu, défensif dans tous les cas** : `showPresentationIfNeeded()` réessaie jusqu'à 15 fois (500ms d'écart, protégé par un verrou `presentationAttemptInFlight` contre les doubles déclenchements concurrents — un bug intermédiaire rencontré et corrigé pendant ce diagnostic, cf. commentaires du code) avant d'abandonner proprement (log d'erreur, pas de crash). Un test de diagnostic (piloté depuis `adb`, pas depuis le code de l'app) a confirmé que désactiver puis réactiver l'écran simulé — forçant un nouvel évènement `onDisplayAdded` sur le process déjà chaud — réussit instantanément ; ce n'est PAS le comportement automatique de l'app aujourd'hui (rien ne force ce cycle depuis le code), juste la preuve utilisée pour diagnostiquer la cause réelle.
- **Piège Kotlin/Android annexe, corrigé au passage** : `MainActivity` plantait avec un `NullPointerException` sur `window.insetsController` quand `applyImmersiveFullscreen()` (Lot 5) était appelée trop tôt dans `onCreate()`, avant que la fenêtre soit attachée — déplacé vers `onWindowFocusChanged()` uniquement (voir Lot 5).

---

## 7. Lot 5 — WebView tactile principale + UI shell

Dépend du Lot 2 (assets frontend disponibles). Indépendant du Lot 4 sur le fond.

### Fichiers concernés
- **(nouveau)** `Activity` principale avec une `WebView` chargeant `/kiosk`, plus un mécanisme de navigation vers l'admin (CDC §2 : « réplique le site à l'identique », pas un simple onglet limité).
- **(nouveau)** gestion du plein écran immersif (`WindowInsetsController`) — quittable, pas de Lock Task (CDC §7).

### Tâches
- [x] `WebView` principale avec JavaScript activé, chargeant `http://127.0.0.2:8000/kiosk/` (Lot 3).
- [x] **Décision retenue pour la navigation vers l'admin, différente de l'intention initiale de ce plan** : pas de barre d'adresse ni d'onglets construits dans l'app — la tablette n'étant PAS verrouillée (CDC §2, décision actée), l'admin reste accessible via le navigateur Chrome normal de la tablette (geste Accueil/multitâche déjà libre, cf. ci-dessous), sans dupliquer un mini-navigateur dans l'app. `MainActivity` reste un raccourci dédié à `/kiosk`, pas un shell multi-pages.
- [x] Plein écran immersif implémenté via `WindowInsetsController` (`WindowInsets.Type.systemBars()`, `BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE`), avec repli `SYSTEM_UI_FLAG_IMMERSIVE` pour compatibilité pré-API 30 — testé fonctionnel sur émulateur (API 37).
- [ ] Télécommande USB HID : **non testable sur émulateur** (pas de port USB physique) — reste à faire sur la tablette pilote (Lot 1).

### Critère de sortie
- [x] Utilisation tactile de `/kiosk` sans barre d'adresse, confirmée sur émulateur. **Nuance par rapport au critère initial** : l'admin n'est pas utilisée « depuis cette même WebView » mais depuis Chrome, accessible librement puisque la tablette n'est pas verrouillée — cohérent avec la décision actée, pas un renoncement.

### Découvertes

**Bug de crash réel trouvé et corrigé** : appeler `applyImmersiveFullscreen()` (qui lit `window.insetsController`) directement dans `onCreate()`, avant `setContentView()`/l'attache réelle de la fenêtre, lève un `NullPointerException` (`getWindowInsetsController() on a null object reference`) — confirmé par crash réel sur émulateur, pas par relecture. Corrigé en déplaçant l'appel dans `onWindowFocusChanged(hasFocus: Boolean)`, qui n'est appelé qu'une fois la fenêtre réellement attachée et focus — et réappliqué à chaque regain de focus (un geste système comme la barre de notifications lève l'immersion temporairement, comportement standard Android, pas un bug).

**Choix explicite de ne pas construire de mini-navigateur dans l'app** (barre d'adresse, onglets) : la décision actée au CDC (« pas de verrouillage ») rend Chrome directement utilisable pour l'admin sans dupliquer cette fonctionnalité dans le code de l'app — évite de construire et maintenir un navigateur web maison alors qu'un vrai en existe déjà sur la tablette. Point à reconfirmer avec l'utilisateur si l'expérience réelle en salle s'avère moins pratique qu'attendu (ex. si un coach préfère rester dans une seule app plutôt que basculer vers Chrome).

---

## 8. Lot 6 — `ForegroundService` persistant

Réf. CDC §7. Dépend du Lot 1 (squelette du service). Les Lots 4 (Presentation) et 5 (WebView tactile) doivent être rattachés à ce service une fois qu'il existe, pas à l'`Activity`.

### Fichiers concernés
- **(nouveau)** `ForegroundService` avec notification persistante (« Bobine diffuse en arrière-plan »).
- Refactor potentiel des Lots 4/5 si leur premier jet vivait dans l'`Activity` : déplacer la propriété du backend Python et de la `Presentation` vers le service, pour qu'ils survivent à la fermeture de l'`Activity`.

### Tâches
- [x] Le service démarre le backend Python (Chaquopy) et possède la `Presentation` HDMI — pas l'`Activity` (`BobineForegroundService.kt`, écrit en même temps que les Lots 4/5, voir Découvertes du Lot 4).
- [x] Notification persistante — canal `bobine_service` (`IMPORTANCE_LOW`), icône, texte, `PendingIntent` pour rouvrir l'app au tap. **Nécessite une demande explicite de la permission runtime `POST_NOTIFICATIONS`** (voir Découvertes) sans quoi le service tourne normalement mais la notification reste invisible.
- [x] Test explicite réel : app supprimée du multitâche (swipe simulé via `adb shell input swipe`, tâche confirmée absente de `dumpsys activity recents`) pendant que l'écran externe est actif → serveur toujours `200 OK` (même PID), `Presentation`/WakeLock/notification tous encore actifs.
- [ ] Test de réouverture après fermeture complète : **non testé explicitement** (comportement attendu par construction — `MainActivity` ne fait que `startForegroundService`, idempotent si déjà démarré — mais pas vérifié avec un test dédié isolant ce cas précis).
- [x] `WakeLock` (`PARTIAL_WAKE_LOCK`, tag `Bobine:hdmiPlayback`) acquis à l'ouverture de la `Presentation`, relâché à sa fermeture — confirmé actif via `dumpsys power` pendant qu'un écran externe est branché, et correctement relâché/racquis en cycle avec les évènements `onDisplayRemoved`/`onDisplayAdded`.

### Critère de sortie
- [x] Scénario CDC §2 vérifié **réellement, pas supposé** : fermeture complète de l'app (tâche retirée du multitâche par un vrai geste simulé) → service, `Presentation` HDMI, WakeLock et notification tous confirmés actifs par inspection système (`dumpsys`), pas seulement par absence de crash apparent.

### Découvertes

**Bug réel trouvé par le test, invisible à la lecture du code : `POST_NOTIFICATIONS` (permission « dangereuse » depuis Android 13) n'est PAS accordée du simple fait de l'avoir déclarée dans le Manifest.** Sans demande explicite à l'exécution, `startForeground()` démarre le service normalement (aucun crash, aucune erreur visible) mais la notification reste invisible — confirmé par `dumpsys notification` montrant `numEnqueuedByApp=5, numPostedByApp=0, numBlocked=5` avant correctif. Corrigé en ajoutant une demande de permission runtime dans `MainActivity` (`registerForActivityResult(ActivityResultContracts.RequestPermission())`, déclenchée dans `onCreate()` si non déjà accordée) — nouvelle dépendance `androidx.activity:activity-ktx`. Après correctif et acceptation par l'utilisateur, `dumpsys notification` confirme `numPostedByApp=1, numOngoing=1`.

**Validation complète par inspection système (`dumpsys`), pas seulement par `curl`** : chaque composant du Lot 6 a été vérifié individuellement après un vrai retrait de tâche du multitâche (`adb shell input keyevent KEYCODE_APP_SWITCH` puis `adb shell input swipe`, absence confirmée dans `dumpsys activity recents`) :
- Serveur : `curl http://127.0.0.1:8000/api/health` → `200 OK`, même PID qu'avant le retrait.
- WakeLock : `dumpsys power` liste `PARTIAL_WAKE_LOCK 'Bobine:hdmiPlayback'` toujours acquis (`isFrozen=false`).
- Notification : `dumpsys notification` confirme `numOngoing=1`.

C'est la preuve la plus solide obtenue jusqu'ici sur ce chantier : pas une supposition sur le comportement d'un `ForegroundService`, un état système réellement inspecté après un vrai geste utilisateur simulé.

---

## 9. Lot 7 — mDNS (`MulticastLock`)

Réf. CDC §5.1. Indépendant des autres lots sur le fond, peut être fait en parallèle dès le Lot 0 validé (dépend juste de `zeroconf` tournant sous Chaquopy).

### Fichiers concernés
- **(nouveau)** acquisition du `MulticastLock` côté Kotlin, dans le `ForegroundService` (Lot 6) au démarrage.
- Aucune modification attendue côté Python (`zeroconf` déjà utilisé tel quel par le backend).

### Tâches
- [x] Acquérir un `WifiManager.MulticastLock` référencé-compté au démarrage du service.
- [x] Vérifier depuis un smartphone du même réseau Wi-Fi que `http://bobine.local:8000` résout et répond. — **non concluant sur émulateur, voir Découvertes.**
- [x] Vérifier le comportement quand l'écran de la tablette est verrouillé/éteint (certains OEM restreignent le multicast écran éteint) — pertinent ici car la tablette n'est pas verrouillée en usage (CDC §2), l'écran peut donc s'éteindre pendant que le service tourne en fond.

### Critère de sortie
- [x] Découverte réseau fonctionnelle depuis un appareil tiers, y compris quand l'écran de la tablette est éteint. — **partiellement validé, voir Découvertes : le verrou et l'enregistrement `zeroconf` sont confirmés actifs écran éteint, mais la résolution bout-en-bout depuis un appareil tiers reste à faire sur la tablette pilote réelle.**

### Découvertes

- `WifiManager.MulticastLock` acquis dans `BobineForegroundService.onCreate()` (`acquireMulticastLock()`), relâché dans `onDestroy()` (`releaseMulticastLock()`) — `setReferenceCounted(false)` comme pour le `WakeLock` du Lot 6 : un seul verrou pour toute la durée de vie du service, pas de comptage par requête (la découverte réseau doit rester possible en permanence). Permission `CHANGE_WIFI_MULTICAST_STATE` déjà présente au Manifest depuis le Lot 0.
- Confirmé tenu via `adb shell dumpsys wifi` (section "Multicast Locks held") : `Multicaster{Bobine:mdns uid=10229}` apparaît dès le démarrage du service, et **reste présent après extinction de l'écran** (`adb shell input keyevent KEYCODE_POWER`, `dumpsys power` confirmant `mWakefulness=Asleep`) — le `ForegroundService` (Lot 6) reste `isForeground=true` dans le même état. Android n'a donc pas révoqué le verrou à l'extinction d'écran sur cet émulateur ; reste à confirmer sur la tablette pilote réelle, certains OEM (notamment certaines Xiaomi/MIUI) étant connus pour appliquer des restrictions multicast plus agressives que l'AOSP stock que fait tourner l'émulateur.
- Le backend (`backend/app/utils/mdns.py`, déjà écrit avant ce lot, aucune modification Python nécessaire) publie bien `bobine.local` avec succès sous Chaquopy : log confirmé `mDNS : 'bobine.local' publié (10.0.2.16:8000, profil Android).` — l'API `zeroconf` utilisée (`Zeroconf`, `ServiceInfo`, `register_service`) est donc compatible avec la version `0.39.4` épinglée pour Android (levait un doute noté au Lot 0, §3.1).
- **Découverte notable, hors périmètre strict du lot mais utile pour le Lot 12** : ce message de log révèle que `platform.system()` renvoie la chaîne **`"Android"`** sous Chaquopy — ni `"Linux"` ni autre chose. `backend/app/utils/deployment.py::get_deployment_profile()` (`DeploymentProfile` actuel : `linux-headless | linux-desktop | windows | macos`) ne gère pas ce cas explicitement ; sur Android, la fonction retombe aujourd'hui sur `"linux-desktop"` par défaut (aucun des artefacts `install.sh` n'existe), ce qui se trouve fonctionner correctement par accident pour `_should_self_publish()` (`!= "linux-headless"` → `True`, mDNS s'auto-publie bien comme souhaité) mais serait fragile pour toute logique future qui distinguerait explicitement desktop/Android. À traiter proprement au Lot 12 (ajouter `"android"` à `DeploymentProfile` et le détecter en premier via `platform.system() == "Android"`).
- **Limite de validation, non résolue dans ce lot** : le réseau virtuel de l'émulateur est NAT côté QEMU (IP publiée `10.0.2.16`, plage `10.0.2.0/24` isolée de l'hôte) — aucun outil mDNS n'est disponible sur la machine de développement (`avahi-resolve`/`avahi-browse` absents) pour tenter une résolution, et même s'ils l'étaient, `10.0.2.16` n'est de toute façon pas routable depuis un « vrai » appareil tiers du réseau local. La résolution bout-en-bout `http://bobine.local:8000` depuis un smartphone/PC tiers sur le même Wi-Fi que la tablette n'a donc **pas pu être validée dans cette session** — même catégorie de limitation que l'USB HID du Lot 5, à couvrir uniquement lors de la validation matérielle réelle (Lot 1, tablette pilote).

---

## 10. Lot 8 — Binaire `ffmpeg`/`ffprobe` ARM64 embarqué

Réf. CDC §9 (correction de l'approche `ffmpeg-kit`). Indépendant des autres lots sur le fond.

### Fichiers concernés
- **(nouveau)** binaires statiques `ffmpeg`/`ffprobe` ARM64, packagés au format `lib*.so` dans `android/app/src/main/jniLibs/arm64-v8a/` (contrainte Android 10+, W^X : un binaire natif ne peut s'exécuter que depuis le répertoire natif de l'app).
- [`backend/app/utils/video_utils.py`](../backend/app/utils/video_utils.py) (lignes 271, 283, 296, 305, 331 — appels `subprocess.run(["ffmpeg", ...])`/`ffprobe`) — pas de changement de logique, seulement le nom/chemin du binaire invoqué doit pouvoir être surchargé (variable d'environnement ou détection de plateforme) pour pointer vers `context.applicationInfo.nativeLibraryDir` sous Android.
- [`backend/app/utils/radio_utils.py`](../backend/app/utils/radio_utils.py) (lignes 143, 180, 192, 240 — mêmes appels) — même remarque.

### Tâches
- [x] Choisir une source de binaires ffmpeg statiques ARM64 — **fait, mais s'avère insuffisant seul, voir Découvertes** : johnvansickle.com (GPLv3, build 7.0.2, réellement statique — confirmé sans section dynamique via `readelf -d`).
- [x] Les packager au format `lib*.so` requis par Android — fait, **avec une découverte non anticipée** : nécessite aussi `packaging.jniLibs.useLegacyPackaging = true` dans `build.gradle.kts` (voir Découvertes), sans quoi le binaire reste compressé dans l'APK et `nativeLibraryDir` est vide au runtime malgré un packaging Gradle réussi.
- [x] Adapter `video_utils.py`/`radio_utils.py` pour résoudre le chemin du binaire dynamiquement — fait via un nouveau module partagé `backend/app/utils/ffmpeg_binaries.py` (`FFMPEG_BIN`/`FFPROBE_BIN`, lus une fois depuis `BOBINE_FFMPEG_BIN`/`BOBINE_FFPROBE_BIN`, repli sur les noms nus inchangé). Kotlin (`BobineForegroundService.kt`) transmet `context.applicationInfo.nativeLibraryDir` à `bobine_bootstrap.start_server_once()`, qui pose ces variables si les fichiers existent réellement.
- [ ] Test réel : import d'une vidéo depuis l'app Android — **bloqué, voir Découvertes** : le binaire est bien trouvé et exécuté, mais tué par le système (`SIGSYS`) avant de produire un résultat.

### Critère de sortie
- [ ] Import vidéo complet fonctionnel depuis l'app Android — **non atteint, bloqué par un mur de sécurité Android identifié mais non contourné dans cette session** (voir Découvertes).

### Découvertes

**Deux problèmes distincts et non anticipés par ce lot tel qu'initialement rédigé, découverts uniquement en testant pour de vrai (pas en lisant la documentation Android) :**

**1. Piège W^X plus subtil que prévu — résolu.** Empaqueter les binaires en `jniLibs/<abi>/lib{ffmpeg,ffprobe}.so` ne suffit PAS à lui seul : par défaut (AGP récent, indépendamment de `minSdk`), Android garde les libs natives **compressées dans l'APK** et les charge en mémoire via `dlopen` sans jamais les extraire sur disque — parfait pour de vraies bibliothèques partagées (c'est ainsi que les `.so` de Chaquopy fonctionnent déjà), mais `context.applicationInfo.nativeLibraryDir` reste alors un dossier **vide**, sans qu'aucune erreur ne soit levée avant l'échec runtime (`FileNotFoundError` côté Python au premier appel `subprocess.run`). Confirmé par inspection directe (`adb shell dumpsys package` → `legacyNativeLibraryDir`, puis `run-as` + `ls`). Corrigé en ajoutant `packaging { jniLibs { useLegacyPackaging = true } }` dans `android/app/build.gradle.kts`, qui force l'extraction classique de toutes les libs natives à l'installation — revérifié après une désinstallation/réinstallation propre (comme pour l'icône du Lot 1, un simple `adb install -r` peut ne pas suffire à faire réévaluer ce genre de réglage) : les deux binaires apparaissent bien, avec le bit exécutable, dans `nativeLibraryDir`.

**2. Mur de sécurité Android identifié PRÉCISÉMENT (pas juste constaté) — cause racine trouvée, binaire de remplacement pas encore choisi.** Une fois le binaire réellement trouvé et lancé, `subprocess.run` échoue systématiquement avec `died with <Signals.SIGSYS: 31>`. **Preuve que ce n'est pas un problème du binaire lui-même** : le même fichier `.so`, poussé et exécuté directement via `adb shell` (`adb push` + `adb shell ... -version`), fonctionne parfaitement. Investigation approfondie menée dans cette session (endpoints de diagnostic temporaires, retirés avant ce commit) :
- Un `os.fork()` direct pour isoler le test a été tenté puis **abandonné après avoir tué le process app entier** (`fork()` sur un process dérivé du zygote Android est fondamentalement dangereux — leçon à ne jamais reproduire). Remplacé par un mini-binaire statique dédié invoqué en `subprocess` (isolation propre, confirmée sans risque).
- **Résultat décisif : même l'appel `getpid` le plus basique échoue** — le crash a lieu **pendant le démarrage du runtime C du binaire lui-même** (avant que `main()` ne soit seulement atteint), pas sur un syscall « exotique » spécifique à un codec. Ce n'est donc PAS une histoire de `mbind`/NUMA/x265 comme on pourrait le supposer.
- **Test décisif, concluant** : un binaire **`busybox` statique musl** (busybox.net, build officiel `1.35.0-x86_64-linux-musl`, confirmé sans section dynamique) exécuté exactement de la même façon (subprocess depuis l'app) **fonctionne** — il s'exécute, analyse ses arguments et écrit une erreur applicative normale sur stderr (`applet not found`, attendu vu son nom renommé en `.so`), sans aucun `SIGSYS`. **Conclusion : le blocage est spécifique aux binaires statiques glibc, pas aux binaires statiques en général.** Le runtime de démarrage glibc (`_start`/`__libc_start_main`) déclenche un appel système que le filtre seccomp-bpf des process app Android (plus restrictif que celui du `shell`, cf. AOSP `bionic/libc/SECCOMP_BLOCKLIST`) tue sans sommation — reproduit à l'identique avec un binaire compilé localement (glibc 2.43, encore plus récent que celui de johnvansickle.com) et avec celui de johnvansickle.com (glibc ~2.24-2.28) : **le problème touche glibc statique en général, pas une version précise**. Aucun tombstone Android n'est généré pour ce crash (`SECCOMP_RET_KILL_PROCESS` sans passage par `debuggerd` ici), donc impossible d'identifier le nom exact du syscall fautif sans `strace`/accès root (indisponibles sur cet émulateur non rooté) — mais ce n'est plus nécessaire : la conclusion actionnable est claire.

**Piste explorée et écartée** : le paquet `ffmpeg` de Termux (`packages.termux.dev`) a été envisagé comme alternative native-Android (Bionic, pas glibc) — mais son métadata (`Depends:` sur ~40 bibliothèques partagées : `libx264`, `libvpx`, `libaom`, etc., toutes gérées dans l'arborescence `$PREFIX` propre à Termux) confirme que ce n'est **pas** un binaire statique autonome ; l'utiliser demanderait d'empaqueter toute cette arborescence de dépendances ET de corriger ses chemins de liaison dynamique — un chantier bien plus lourd que prévu, non entamé.

**Prochaine étape, bien plus ciblée qu'avant cette session : trouver (ou construire) un ffmpeg/ffprobe statique musl ARM64**, pas glibc. Recherches faites dans cette session pour une source déjà prête, sans succès :
- johnvansickle.com : glibc, écarté (cause du blocage).
- BtbN/FFmpeg-Builds ("linuxarm64-gpl") : en réalité **dynamiquement lié contre glibc** malgré le nom "gpl" (qui ne concerne que la liaison interne des libs ffmpeg, pas la liaison système) — jamais utilisable ici, écarté avant même le test seccomp.
- ffmpeg.martin-riedl.de : dynamiquement lié aussi, écarté.
- Aucune source équivalente à johnvansickle.com mais pour musl n'a été trouvée pour ffmpeg spécifiquement (busybox, lui, en propose — cf. busybox.net — mais ffmpeg est un projet bien plus lourd, moins souvent packagé en musl statique par la communauté).

**Deux chemins concrets pour la suite, par ordre de rapidité probable** :
1. Compiler ffmpeg soi-même avec un toolchain musl portable (ex. `musl.cc`, cross-compilateurs prêts à l'emploi sans installation système/root) — nécessite `ffmpeg configure --enable-static --disable-shared` avec ce toolchain ; un build minimal (décodeurs natifs H.264/AAC déjà inclus sans libx264, seul un encodeur H.264 nécessiterait une lib externe type x264 à compiler aussi en musl) pourrait suffire aux besoins réels de Bobine (vignette = décodage seul, `ffprobe` = lecture seule) — à vérifier lesquelles des opérations `normalize_video`/`transcode_to_web` ont réellement besoin d'un encodeur externe avant de statuer sur le périmètre exact du build.
2. Compiler ffmpeg nativement pour Android via le NDK (dans l'esprit de `ffmpeg-android-maker`) — solution la plus robuste à terme (binaire pensé pour Bionic dès l'origine) mais toolchain/autotools cross-compilation plus lourde à mettre en place.

**Ce qui reste solide et réutilisable indépendamment du binaire final retenu** : le mécanisme de résolution de chemin (`ffmpeg_binaries.py`, variables d'environnement posées par `bobine_bootstrap.py`) et le fix `useLegacyPackaging` sont corrects et déjà validés (32 tests backend toujours verts, comportement desktop inchangé) — seule la question du **binaire lui-même** reste ouverte, mais avec un critère de sélection net désormais (musl, pas glibc). `android/app/src/main/jniLibs/` est gitignored (comme `ffmpeg.exe`/`ffprobe.exe` pour Windows dans `ci.yml`, jamais commités) ; aucune étape CI n'a été ajoutée à `android-build` tant qu'aucun binaire fonctionnel n'est confirmé.

---

## 11. Lot 9 — Stockage médias & USB OTG

Réf. CDC §5.2. Dépend du Lot 1 (structure de l'app).

### Fichiers concernés
- Configuration du chemin `media_dir`/`watch_dir` (`config.toml` / variables `BOBINE_*`) pointant vers `context.getExternalFilesDir(null)` sous Android — pas de changement de `backend/app/config.py` lui-même, seulement de la valeur injectée au démarrage.
- **(nouveau)** gestion Kotlin de la détection d'un périphérique USB OTG branché sur le dock (Storage Access Framework ou détection de point de montage, à trancher selon ce que permet Android 16 sans root).

### Tâches
- [x] Confirmer l'espace disponible réel et les permissions sur `getExternalFilesDir` (pas de demande de permission intrusive requise, à vérifier empiriquement).
- [~] Implémenter la détection et l'exposition d'une clé USB branchée sur le dock comme source d'import, côté UI — voir Découvertes : probablement déjà couvert par l'architecture existante (Lot 5), mais non testé faute de périphérique USB OTG physique dans cette session.

### Critère de sortie
- [ ] Import d'un fichier vidéo depuis une clé USB branchée sur le dock, bout en bout — reste à faire avec un vrai périphérique OTG.

### Découvertes

**Bug réel trouvé et corrigé, indépendant de tout matériel USB OTG** : sans intervention, `_data_root()` (`backend/app/config.py`) ne gérait aucun cas `platform.system() == "Android"` et retombait sur le repli final `ROOT_DIR` — qui, sous Chaquopy, pointe vers `AssetFinder/app/`, le dossier interne **privé** où Chaquopy **redéploie les sources Python de l'app elle-même à chaque mise à jour**. Toutes les données utilisateur (vidéos, `database.db`, dossiers surveillés) y auraient donc été stockées mélangées avec le code source de l'app — invisibles depuis un gestionnaire de fichiers, et à risque d'être écrasées ou perdues à la prochaine mise à jour de l'APK (confirmé en pratique au Lot 2 : c'est exactement ce chemin, `/data/data/com.bobine.app/files/chaquopy/AssetFinder/app/data/...`, qui apparaissait dans les logs `Watcher : Initialisation sur ...` jusqu'à ce lot).

**Corrigé par trois changements coordonnés, minimaux, dans le sens Kotlin → Python** :
1. `BobineForegroundService.kt` (`onCreate()`) : passe désormais `applicationContext.getExternalFilesDir(null)?.absolutePath` à `bobine_bootstrap.start_server_once(...)`.
2. `android/app/src/main/python/bobine_bootstrap.py` : accepte ce chemin en paramètre et pose la variable d'environnement `BOBINE_ANDROID_DATA_DIR` **avant** le premier `from app.main import app` (le seul moment où ça compte, `DATA_ROOT` étant calculé une fois au niveau module dans `config.py`).
3. `backend/app/config.py::_data_root()` : nouvelle branche `elif platform.system() == "Android":` (aux côtés des branches Windows/Darwin/Linux déjà existantes) qui lit cette variable et l'utilise comme racine si présente. **Écart assumé par rapport au texte initial de ce lot** (« pas de changement de `backend/app/config.py` ») : après lecture du code réel, `_data_root()` est le point d'entrée naturel et déjà utilisé par toutes les autres plateformes pour exactement ce même problème — dupliquer la logique dans `bobine_bootstrap.py` via des surcharges `BOBINE_<CHAMP>_DIR` individuelles (mécanisme générique déjà existant, cf. `env_prefix = "BOBINE_"`) aurait marché aussi, mais en dupliquant les 12 sous-chemins relatifs (`data/videos`, `data/watched`...) qui vivent déjà comme valeurs par défaut dans `Settings` — plus fragile aux dérives futures qu'une seule branche `elif` suivant le patron existant.

**Validé sur émulateur** (recréation de l'AVD entre-temps, écran externe simulé conservé du Lot 4) : après réinstallation, les logs confirment `Watcher : Initialisation sur /storage/emulated/0/Android/data/com.bobine.app/files/data/watched` (et équivalents pour `backgrounds_watched`/`audio_watched`/`radio_watched`) — **plus** `AssetFinder/app/data/...`. `adb shell ls -la .../files/data/` confirme la structure complète créée avec les bonnes permissions (`u0_a229:ext_data_rw`, `drwxrws---` — accès `run-as`/app uniquement, pas de permission `READ/WRITE_EXTERNAL_STORAGE` intrusive nécessaire, comme attendu pour du stockage externe **spécifique à l'app**) : `database.db` (+ `-shm`/`-wal`), `videos/`, `watched/`, `thumbnails/`, `backgrounds/`, `backgrounds_watched/`, `audio/`, `audio_watched/`, `branding/`, `logs/`, `radio/`, `radio_covers/`, `radio_announcements/`, `radio_watched/`, `tmp/`.

**USB OTG (deuxième tâche du lot) : non implémenté explicitement, probablement déjà couvert sans code supplémentaire, mais NON TESTÉ faute de périphérique OTG physique disponible dans cette session.** Le Lot 5 a délibérément choisi de ne construire aucun mini-navigateur natif pour l'admin (accès via Chrome). Le flux d'upload existant du frontend passe par un `<input type="file">` HTML standard — sur Android, ce type de champ ouvre nativement le sélecteur de documents du système (Storage Access Framework), qui liste automatiquement tout périphérique de stockage monté, y compris une clé USB OTG reconnue par Android, **sans code spécifique à Bobine**. Reste néanmoins à confirmer avec une vraie clé USB + le dock réel : Android doit d'abord reconnaître et monter le périphérique (peut dépendre du système de fichiers de la clé — FAT32/exFAT généralement supportés nativement, NTFS pas toujours), ce qui est indépendant du code de l'app.

**Non résolu, hors périmètre de ce lot** : en observant les logs de cette session, l'erreur d'hydratation React déjà connue (`task_67d56a94`) provoque au démarrage de `/cinema` une rafale d'une **cinquantaine de reconnexions WebSocket en moins de 2 secondes** (`Client WebSocket connecté` incrémentant très vite avant de se stabiliser) — un symptôme plus visible que le simple message d'erreur logué observé aux lots précédents, mais qui se stabilise ensuite normalement (pas une boucle infinie). À signaler pour la tâche séparée, pas à corriger ici.

---

## 12. Lot 10 — Device Owner (provisioning, exemption batterie)

Réf. CDC §7. Peut être fait en parallèle des Lots 4-9, mais son test réel nécessite une tablette pouvant être remise à l'état d'usine (attention, opération destructive sur la tablette pilote si elle sert déjà à autre chose — confirmer avec l'utilisateur avant d'exécuter ce lot sur du matériel en cours d'usage).

### Fichiers concernés
- **(nouveau)** `DeviceAdminReceiver` minimal (Device Owner sans Lock Task).
- **(nouveau)** procédure de provisioning documentée (`adb shell dpm set-device-owner ...`).

### Tâches
- [ ] Implémenter un `DeviceAdminReceiver` qui ne fait qu'exempter l'app des restrictions batterie — pas de politique de restriction supplémentaire imposée à l'utilisateur.
- [ ] Documenter la procédure de provisioning exacte (tablette réinitialisée en usine → pas de compte configuré → `adb shell dpm set-device-owner ...` avant tout autre setup).
- [ ] Test réel sur HyperOS (tablette pilote) : le service survit-il à une inactivité prolongée (heures) sans interaction utilisateur, comparé au comportement sans Device Owner ?

### Critère de sortie
- [ ] Survie du service vérifiée sur au moins 24h d'inactivité sur la tablette pilote, avec Device Owner actif.

### Découvertes
*(à compléter par l'agent qui exécute ce lot)*

---

## 13. Lot 11 — Mécanisme de mise à jour in-app

Réf. CDC §8. Dépend du Lot 13 (existence de releases GitHub réelles à détecter).

### Fichiers concernés
- **(nouveau)** code Kotlin de vérification de version + téléchargement + déclenchement d'installation (`REQUEST_INSTALL_PACKAGES`).
- Potentiellement `backend/app/routers/updates.py` si le mécanisme choisi réutilise un endpoint commun avec le desktop plutôt que d'interroger directement l'API GitHub Releases — à trancher par l'agent qui exécute ce lot et à documenter dans Découvertes.

### Tâches
- [ ] Décider et documenter la source de vérité de version (API GitHub Releases directement, ou endpoint `bobine.fit` existant, ou nouveau).
- [ ] Implémenter la vérification périodique + le téléchargement de l'APK.
- [ ] Demander `REQUEST_INSTALL_PACKAGES` et déclencher l'installation, avec confirmation utilisateur (Android exige une interaction explicite pour ce type d'installation hors store).
- [ ] Test réel : publier une version factice supérieure, vérifier la détection et l'installation bout en bout sur la tablette pilote.

### Critère de sortie
- [ ] Mise à jour d'une version factice vers une autre, sans intervention manuelle autre que la confirmation d'installation.

### Découvertes

**Pré-requis technique posé en amont de ce lot (pas le lot lui-même)** : `versionCode`/`versionName` étaient jusqu'ici des constantes figées dans `android/app/build.gradle.kts` (`1` / `"0.1.0-dev"`), contrairement à toutes les autres plateformes qui reçoivent déjà `VERSION`/`COMMIT` injectés dynamiquement par le job `version` de `ci.yml` (canal Stable via tag `Vx.y.z` vs. canal Bêta `x.y.z-beta` à chaque push sur `main`). Corrigé : `build.gradle.kts` lit désormais `ANDROID_VERSION_NAME`/`ANDROID_VERSION_CODE` depuis l'environnement (repli sur les anciennes constantes si absentes, donc aucun changement pour un build local hors CI). Le job `android-build` de `ci.yml` positionne :
- `ANDROID_VERSION_NAME = needs.version.outputs.display_version`, exactement le même format `x.y.z`/`x.y.z-beta` que Windows/macOS/Linux — pas de format Android-spécifique inventé.
- `ANDROID_VERSION_CODE = git rev-list --count HEAD` (nécessite `fetch-depth: 0` sur ce job, ajouté ici) — un entier strictement croissant à chaque commit sur `main`, condition qu'Android impose pour accepter une mise à jour par-dessus une installation existante. Un tag Stable pointant toujours sur un commit de `main`, la propriété de croissance est préservée entre canaux (jamais de retour en arrière).

Validé localement : `ANDROID_VERSION_NAME="3.0.1-beta" ANDROID_VERSION_CODE="123" ./gradlew :app:assembleDebug` puis `aapt dump badging` confirme `versionCode='123' versionName='3.0.1-beta'` dans l'APK réellement produit ; sans ces variables, retombe bien sur `versionCode='1' versionName='0.1.0-dev'`. Ce mécanisme est un pré-requis pour ce lot (une vraie mise à jour in-app a besoin d'un `versionCode` significatif à comparer), pas une implémentation du lot lui-même — la vérification périodique, le téléchargement et `REQUEST_INSTALL_PACKAGES` restent entièrement à faire, et dépendent toujours de la publication publique réelle des releases Android (actuellement différée, cf. Lot 13).

---

## 14. Lot 12 — Documentation & contexte agents IA

Transverse, peut être fait au fil de l'eau à chaque lot livré plutôt qu'à la fin — chaque lot devrait déjà mettre à jour ce qui le concerne directement dans le CDC ou l'architecture, ce lot couvre ce qui reste global.

### Fichiers concernés
- [`README.md`](../README.md) / [`README.fr.md`](../README.fr.md) — ligne Android actuellement « Coming soon » à mettre à jour une fois l'APK publiable.
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — ajouter une mention du profil Android une fois qu'il existe réellement (probablement un nouveau `deployment_profiles/android.py` si le mécanisme `get_deployment_profile()` de [`backend/app/utils/deployment.py`](../backend/app/utils/deployment.py) doit distinguer ce profil — à évaluer : Android tourne sous Linux au niveau noyau, `platform.system()` renverra `"Linux"`, donc une détection dédiée sera nécessaire si le comportement doit diverger du profil `linux-headless`/`linux-desktop` existant).
- `.agents/AGENTS.md`, `.agents/CLAUDE.md`, `.gemini/AGENTS.md` — contexte agents IA, si le chantier introduit des conventions à connaître pour les futurs agents (ex. présence du dossier `android/`).

### Tâches
- [x] Vérifier si `get_deployment_profile()` a besoin d'un cas Android explicite — **oui, confirmé nécessaire** (voir Découvertes) : `platform.system()` renvoie en réalité `"Android"` sous Chaquopy, pas `"Linux"` comme supposé par ce lot à sa rédaction initiale.
- [ ] Mettre à jour le tableau de téléchargement du README une fois l'APK publié sur GitHub Releases (toujours différé, cf. Lot 13).
- [ ] Mettre à jour `docs/ARCHITECTURE.md` avec la stack Android réelle une fois le portage plus avancé.

### Critère de sortie
- [ ] Aucune mention obsolète de « Coming soon » ou de plan prospectif dans les docs une fois le portage livré.

### Découvertes

**La prémisse de ce lot était fausse, corrigée après lecture réelle du code** : ce lot supposait que `platform.system()` renverrait `"Linux"` sous Android (noyau Linux) et se demandait si une détection dédiée serait nécessaire « si le comportement doit diverger ». En réalité (confirmé au Lot 7 par les logs `mDNS : 'bobine.local' publié (..., profil Android)`, et revérifié ici via `/api/settings`), Chaquopy fait remonter **`"Android"`** explicitement — `get_deployment_profile()` (`backend/app/utils/deployment.py`) ne gérait donc AUCUN cas Android et retombait sur le repli final `"linux-desktop"`, qui fonctionnait par accident pour `mdns.py::_should_self_publish()` (`!= "linux-headless"` reste vrai) mais aurait été franchement incorrect pour `get_profile_handler()` : le repli de cette fonction route tout profil non reconnu vers `LinuxHeadlessHandler` (appels `systemctl`/`sudo` inexistants sur Android — auraient échoué silencieusement ou plané selon le point d'entrée).

**Corrigé par une nouvelle branche + un nouveau handler, au même endroit et avec la même forme que les branches Windows/Darwin/macOS existantes** — pas d'exception, pas de cas particulier ailleurs dans le code :
- `DeploymentProfile` inclut désormais `"android"` ; `get_deployment_profile()` teste `platform.system() == "Android"` avant le repli Linux headless/desktop.
- **(nouveau)** `backend/app/utils/deployment_profiles/android.py` (`AndroidHandler`) : `restart_services()` fait `os._exit(0)` comme Windows/macOS/Linux desktop, mais **sans garantie de relance immédiate** — contrairement aux autres profils, il n'existe aucun superviseur léger (BobineTray, systemd --user) qui relance le sous-processus ; seul `START_STICKY` (Lot 6) donne une chance de relance du `Service`, sans garantie de délai ni de relance de l'UI visible (`MainActivity`). Les 3 seuls appelants (`_run_full_reset`, restauration de sauvegarde, remise à zéro d'usine) restent des actions admin délibérées et rares, jamais déclenchées par un simple enregistrement de réglage — c'est le choix le moins mauvais en l'absence d'un mécanisme de relance dédié (Lot 10 serait l'endroit naturel pour fiabiliser ça). `apply_update()` lève `UpdateUnsupported` comme les autres profils sans mise à jour automatique. `can_self_uninstall()` = False, `uninstall_instructions()` pointe vers la désinstallation standard Android (pas de mécanisme spécifique à construire).
- `get_profile_handler()` route explicitement `"android"` vers `AndroidHandler` (nouvelle branche `elif`, même patron que les autres profils).

**Non testé dans cette session, à valider avant de faire confiance à ce chemin en production** : aucun des 3 appelants de `restart_services()` (reset complet, restauration, remise à zéro d'usine) n'a été déclenché réellement sur émulateur ou tablette — seule la détection du profil (`/api/settings` → `"deployment_profile": "android"`, confirmé) et l'absence de crash au démarrage ont été vérifiées. Un vrai test du bouton "Réinitialisation complète" (ou équivalent) sur la tablette pilote reste à faire pour savoir si le kiosque revient réellement seul après coup, ou reste noir en attendant une réouverture manuelle de l'app.

**`routers/updates.py`** : la boucle `if profile == "windows"/"linux-desktop"/"macos"` qui choisit l'extension d'asset à télécharger (`.exe`/`.deb`/`.dmg`) ne gère pas `"android"` explicitement — **volontairement laissé tel quel**, `target_ext` reste `None` pour ce profil (comme pour `"linux-headless"`), donc `download_url` retombe proprement sur la page GitHub Releases (`html_url`) plutôt que de planter ou de proposer un mauvais lien — cohérent avec le Lot 13 (aucun asset Android public à proposer pour l'instant).

---

## 15. Lot 13 — Signature APK, CI, publication GitHub Releases

Réf. CDC §2. Dépend de tous les lots produisant du code fonctionnel (peut démarrer dès qu'il y a un APK installable à signer, même incomplet, pour roder le pipeline tôt).

### Fichiers concernés
- **(nouveau)** clé de signature auto-générée, gérée comme un secret GitHub Actions (jamais commitée).
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — nouveau job de build/signature/publication Android, en miroir des jobs existants Windows/macOS/Linux.

### Tâches
- [x] Clé de signature dédiée générée (`keytool`, RSA 4096, PKCS12, alias `bobine`, validité jusqu'en 2054) — **hors dépôt**, dans `~/.bobine-signing/` sur la machine où elle a été créée, avec un `README.md` documentant sa conservation et l'avertissement qu'une perte empêche toute mise à jour future du même `applicationId`. Les 4 secrets GitHub Actions correspondants (`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`) sont configurés sur le dépôt.
- [x] Job CI `android-build` ajouté à `.github/workflows/ci.yml` — **décision explicite, différente du plan initial** : PAS suffixé/publié dans la release Bêta publique pour l'instant (voir Découvertes). Reste un artefact CI téléchargeable.
- [x] Vérifié : l'APK signé (clé dédiée, pas la clé debug) s'installe proprement sur l'émulateur (`adb install` après `adb uninstall` de la version debug — pas de conflit de signature, pas d'avertissement).

### Critère de sortie
- [x] **Adapté à la décision ci-dessus** : le job CI produit bien un APK signé à chaque push (une fois les secrets configurés, ce qui est fait), vérifié installable — mais rien n'est encore publié sur GitHub Releases par choix, pas par contrainte technique. Un vrai tag de release stable/bêta ne déclenche donc PAS encore de publication Android tant que cette décision n'est pas révisée (cf. Découvertes).

### Découvertes

**Décision structurante qui diverge du plan initial : l'APK Android n'est PAS ajouté aux assets des releases Stable/Bêta publiques**, contrairement à ce que ce plan prévoyait (« suffixé `-beta`, cohérent avec le canal Bêta desktop »). Le portage est encore en chantier (Lots 4 à 12 non faits : pas de `ForegroundService`, pas de double affichage, pas de verrouillage kiosque) — publier maintenant risquerait de faire croire aux utilisateurs suivant le canal Bêta que l'Android est utilisable en salle, alors que ce n'est pas le cas. Le job `android-build` construit et signe malgré tout à chaque push (roder le pipeline tôt, comme prévu), mais seulement comme artefact CI téléchargeable depuis l'onglet Actions — `release-stable`/`release-beta` ne le référencent volontairement pas dans leur `needs:`. À revoir explicitement quand le portage sera prêt pour de vrais utilisateurs.

**Le job ne fait pas échouer la CI si les secrets ne sont pas configurés.** Cohérent avec l'intention affichée en tête de `ci.yml` (« volontairement léger et fiable pour un statut vert stable ») : une vérification précoce (`check_secrets`) fait sauter proprement toutes les étapes suivantes avec un `::warning::` plutôt que de faire échouer la CI sur tous les pushes tant que les secrets ne sont pas configurés. Dans ce cas précis, les secrets ONT été configurés dans ce même lot, donc le job s'exécutera réellement dès le prochain push — mais ce garde-fou reste utile pour la reproductibilité (ex. un fork du dépôt sans ces secrets).

**Format PKCS12 : un seul mot de passe pour le keystore ET la clé**, pas deux séparés — `keytool` récent ignore silencieusement un `-keypass` différent du `-storepass` sur ce format (avertissement explicite à la génération). Documenté dans `~/.bobine-signing/README.md` pour ne pas surprendre un futur agent qui s'attendrait à deux mots de passe distincts.

**Le job CI a échoué deux fois de suite au premier vrai déclenchement, corrigé les deux fois en regardant le vrai log — pas en relisant la config a priori** :
1. `sdkmanager: command not found` — le runner `ubuntu-latest` de GitHub Actions n'expose pas `sdkmanager` sur le `PATH` par défaut malgré un SDK Android préinstallé. Corrigé avec l'action `android-actions/setup-android@v3` (configure `ANDROID_HOME`/`PATH`/licences correctement) avant d'installer `platforms;android-36`/`build-tools;36.1.0` via `sdkmanager`.
2. `sh: 1: next: not found` — la tâche Gradle `buildFrontendStatic` (Lot 2) suppose que `frontend/node_modules` existe déjà (vrai en local, jamais vrai sur un checkout CI frais). Corrigé en ajoutant une étape explicite `npm ci` dans le job, comme le font déjà `windows-build`/`frontend`.

**Confirmé sur un vrai run CI, pas seulement en local** (3ᵉ tentative, run [34278925876](https://github.com/FantasmaGlad/Bobine/actions/runs/34278925876)) : `apksigner verify --print-certs` sur l'APK produit par le job affiche bien `CN=Bobine` (la clé dédiée, pas une clé de test), artefact `bobine-android-apk-<commit>` uploadé avec succès (~43 Mo). Le pipeline de signature est donc opérationnel de bout en bout, pas seulement documenté.

**Build release testé pour de vrai, pas seulement en théorie** : `ANDROID_KEYSTORE_PATH`/`ANDROID_KEYSTORE_PASSWORD`/`ANDROID_KEY_ALIAS`/`ANDROID_KEY_PASSWORD` exportés en local, `./gradlew :app:assembleRelease` réussi, signature vérifiée avec `apksigner verify --print-certs` (`CN=Bobine`, pas le certificat `CN=Android Debug` des builds précédents), et installation propre sur l'émulateur après désinstallation de la version debug.

---

## 16. Séquencement

1. **Lot 0** en premier, isolément — rien d'autre ne doit démarrer avant sa décision go/no-go écrite.
2. **Lot 1**, dépend du Lot 0. Une fois livré, plusieurs lots peuvent démarrer **en parallèle** :
   - **Lot 2** (frontend embarqué) — indépendant, peut même démarrer dès le Lot 0 si un projet Android jetable existe déjà pour le tester.
   - **Lot 7** (mDNS) — indépendant, dépend juste de Chaquopy/`zeroconf` validés au Lot 0.
   - **Lot 8** (ffmpeg statique) — indépendant du reste de l'app Android, peut être préparé et testé isolément.
   - **Lot 10** (Device Owner) — indépendant sur le code, mais son test réel nécessite de sacrifier une tablette réinitialisée (coordination matérielle avec l'utilisateur avant de commencer, cf. avertissement du Lot 10).
3. **Lot 3** (routage hostname) — dépend conceptuellement du Lot 2 (il faut du contenu à router) mais pas de code réellement partagé ; peut être tranché tôt en parallèle.
4. **Lot 4** (double affichage) — dépend des Lots 1 et 3.
5. **Lot 5** (WebView tactile) — dépend du Lot 2, indépendant du Lot 4 sur le fond, mais les deux convergent au **Lot 6**.
6. **Lot 6** (`ForegroundService` persistant) — dépend des Lots 4 et 5 (il doit prendre possession de ce qu'ils ont produit). **Point de convergence obligatoire** avant le Lot 9 (persistance du stockage doit être vérifiée avec le service définitif, pas un service provisoire).
7. **Lot 9** (stockage/USB OTG) — dépend du Lot 1, peut suivre le Lot 6 sans urgence particulière.
8. **Lot 12** (documentation) — au fil de l'eau à chaque lot, pas un lot isolé en fin de chantier malgré sa numérotation.
9. **Lot 13** (signature/CI) — peut démarrer dès qu'un APK installable existe (même incomplet), pour roder le pipeline tôt plutôt que de le découvrir en fin de chantier.
10. **Lot 11** (mise à jour in-app) — en dernier, dépend du Lot 13 (releases réelles à détecter).

---

## 17. Checklist exhaustive (vue transverse anti-oubli)

- [x] Lot 0 — go/no-go dépendances Chaquopy (GO — downgrade Pydantic v1 sur Android, watchdog en polling maison)
- [~] Lot 1 — squelette projet (fait) + première installation réelle sur tablette pilote faite (icône + cleartext corrigés) ; dock/HDMI physique encore à faire (pas simulable sur émulateur)
- [x] Lot 2 — frontend statique embarqué (GO — confirmé visuellement sur émulateur)
- [~] Lot 3 — routage hostname `/kiosk` vs `/cinema` (décision 127.0.0.2 validée ; vérification bascule bloquée par un bug hors-périmètre, `task_67d56a94`)
- [x] Lot 4 — double affichage `DisplayManager`/`Presentation` (validé émulateur, hotplug réel ; cold-boot-avec-écran-déjà-présent à revérifier sur tablette)
- [x] Lot 5 — WebView tactile + UI shell + plein écran immersif quittable (admin via Chrome, pas de mini-navigateur maison — décision actée)
- [x] Lot 6 — `ForegroundService` persistant (survit à la fermeture de l'app — vérifié par `dumpsys`, pas supposé)
- [x] Lot 7 — mDNS (`MulticastLock`)
- [~] Lot 8 — infrastructure prête (résolution de chemin, useLegacyPackaging) ; bloqué sur le choix du binaire lui-même (SIGSYS seccomp app, voir Découvertes)
- [~] Lot 9 — stockage médias (getExternalFilesDir, validé émulateur) ; USB OTG probablement déjà couvert par le SAF mais non testé (pas de périphérique physique)
- [ ] Lot 10 — Device Owner sans Lock Task
- [ ] Lot 11 — mise à jour in-app (pré-requis versionCode/versionName dynamiques posé ; vérification/téléchargement/installation restent à faire)
- [~] Lot 12 — deployment.py gère désormais un profil "android" explicite (AndroidHandler) ; README/ARCHITECTURE.md restent à mettre à jour une fois le portage plus avancé
- [x] Lot 13 — signature APK, CI (build+signature à chaque push) ; publication publique volontairement différée (décision actée, cf. Découvertes)

---

## 18. Risques et points de vigilance

- **Lot 0 non concluant** — si `pydantic-core` n'a pas de wheel Android exploitable et qu'aucun contournement simple n'existe, tout le chantier doit être remis en question (l'alternative serait de downgrader Pydantic/FastAPI, avec un impact potentiellement large sur le backend partagé avec les autres plateformes — **ne jamais faire ce choix dans le seul contexte du Lot 0** sans évaluer l'impact sur `backend/app/` dans son ensemble).
- **`ffmpeg-kit-android` non retenu, mais son remplaçant (binaire statique bundlé) n'est pas encore validé non plus** (Lot 8) — c'est un risque réel, pas juste une correction cosmétique de ce document.
- **Survie du service en arrière-plan sur HyperOS/One UI** — le Device Owner sans Lock Task (Lot 10) est la meilleure piste connue, mais n'est validée par aucun test réel avant l'exécution de ce lot. Prévoir un plan de repli (ex. notification incitant l'utilisateur à rouvrir l'app) si la survie 24/7 s'avère insuffisante même avec Device Owner.
- **Provisioning Device Owner sur du matériel déjà en service** — `dpm set-device-owner` exige une tablette vierge ; si la tablette pilote sert déjà à d'autres tests au moment du Lot 10, coordonner avec l'utilisateur avant toute réinitialisation.
- **Décodage AV1 non garanti** — ne pas supposer un décodage matériel universel si le catalogue de cours venait à inclure de l'AV1 (CDC §3.3).
- **Régression du routage hostname existant** — le Lot 3 touche un mécanisme ([`useDisplayOutputRedirect.ts`](../frontend/src/lib/useDisplayOutputRedirect.ts)) partagé avec le desktop x86 actuel en production. Toute modification doit être testée aussi contre le comportement desktop existant (câblé/réseau), pas seulement contre le nouveau cas Android, pour ne pas régresser une fonctionnalité en production.
- **Clé de signature APK perdue** — bloquerait toute mise à jour future du même `applicationId` sur les tablettes déjà déployées ; sa conservation (Lot 13) n'est pas un détail secondaire.
