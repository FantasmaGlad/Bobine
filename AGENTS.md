# AGENTS.md — Bobine

Ce fichier est le guide d'orientation principal, **canonique et versionné**, pour les agents IA (Antigravity, Gemini, Claude, etc.) travaillant dans ce dépôt. Il fusionne l'ancien contenu dupliqué de `.agents/AGENTS.md` et `.agents/CLAUDE.md` (tous deux gitignorés, donc invisibles à quiconque clone le dépôt) en une seule source de vérité, désormais suivie par git.

- `.claude/CLAUDE.md` et `.gemini/AGENTS.md` sont de simples redirections locales (non versionnées) vers ce fichier, pour les outils qui cherchent spécifiquement ces noms.
- `.agents/local-env.md` (non versionné) contient l'environnement réseau réel du mainteneur (hostnames/IP personnels) — ne pas y placer d'information nécessaire à la compréhension du projet par un tiers, cf. §2 ci-dessous.

---

## 1. Directives d'Ingénierie, Vision Long Terme & Règles d'Efficacité

### 1.1 Vision d'Implémentation Long Terme & Zéro Devinette
1. **Zéro supposition, zéro devinette** : Ne JAMAIS formuler d'affirmations infondées, devinées ou spéculatives. Tout diagnostic technique doit être prouvé empiriquement par des faits vérifiables : lecture directe des logs, inspection du code source existant, requêtes API réelles (`curl`), exploration du schéma de base de données ou vérification des fichiers système (`/proc`, `/sys`, etc.). Si une information manque, réaliser un audit exhaustif préalable avant d'agir.
2. **Recherche de la cause racine systémique** : Bannir les "pansements" court terme, les hacks superficiels ou le masquage d'erreurs (ex: un try/except silencieux masquant un type `undefined`). Tout problème doit être résolu à sa source d'architecture pour garantir une stabilité durable dans le temps.
3. **Conception modulaire, découplée et pérenne** :
   - Écrire un code hautement lisible, découplé, fortement typé (TypeScript strict / schémas Pydantic) et prévisible.
   - Documenter systématiquement le *pourquoi* des choix techniques, des contraintes d'OS et des mécanismes de repli, afin que les développeurs et agents futurs comprennent immédiatement la logique sans régressions.
4. **Discipline Git & Neutralité Stricte** :
   - **Format Conventional Commits obligatoire en minuscules** avec scope : `type(scope): description concise à l'infinitif` (ex: `feat(hardware): ...`, `fix(metrics): ...`, `docs(spec): ...`, `chore(release): ...`).
   - **Corps de message** : Liste à puces détaillant les causes racines résolues, les mécanismes introduits et les tests effectués.
   - **Zéro co-auteur, zéro mention d'IA** : Ne JAMAIS inclure de balise `Co-authored-by`, ni mentionner d'assistant ou d'IA dans les commits, la documentation ou le code source.
5. **Conservation de l'architecture** :
   - Respecter le modèle mono-processus Uvicorn + SQLite (Redis supprimé depuis PortabiliteCrossPlatformX Lot 0, cf. `docs/ARCHITECTURE.md`).
   - Préserver la séparation des deux canaux de diffusion (Câblé / Réseau).

### 1.2 Matrice d'Audit et de Validation Multi-OS Universelle
Bobine cible **5 profils d'exécution réels** en production. Toute modification touchant au système (hardware, télémétrie, veille, fenêtrage, son, stockage, processus, réseau) DOIT être auditée et implémentée pour **chacun** de ces 5 profils :
1. **Android ARM64 (`.apk`, Chaquopy, API 34-36)** :
   - *Spécificités* : Restrictions du bac à sable `seccomp-bpf` (fork du zygote applicatif), double racine de stockage (interne `filesDir` F2FS vs externe FUSE pour les médias), cycle de vie `ForegroundService`, pas de privilèges root, configuration réseau `network_security_config`.
   - *Télémétrie/Matériel* : Lecture des propriétés `ro.soc.model`, `ro.board.platform`, nœuds sysfs `/sys/class/kgsl/` (GPU) et `/sys/class/thermal/` (températures).
2. **Linux Bureau (`.deb`, APT `apt.bobine.fit`)** :
   - *Spécificités* : Session utilisateur non root, serveurs graphiques X11 ou Wayland, systray XDG, service utilisateur `systemctl --user`, intégration Polkit.
   - *Télémétrie/Matériel* : SMBIOS sans root via `udevadm info -p /devices/virtual/dmi/id`, `/proc/cpuinfo`, sysfs drm/hwmon.
3. **Appliance Headless (Dell Wyse 5070 / mini-PC, `install.sh`)** :
   - *Spécificités* : Debian 13 dédiée, services systemd système (`bobine-backend.service`, `bobine-kiosk.service`), Chromium X11 plein écran sans bureau, pilotage écran HDMI/DisplayPort.
   - *Télémétrie/Matériel* : Sysfs `intel-rapl` pour la puissance en Watts, `hwmon`, `lsblk` / sysfs block.
4. **Windows Desktop (`.exe`, Inno Setup)** :
   - *Spécificités* : Exécutable silencieux sans console noire (`console=False`, `CREATE_NO_WINDOW`), intégration systray Win32, mode clamshell sans veille via `powercfg`.
   - *Télémétrie/Matériel* : Registre Windows `CentralProcessor\0\ProcessorNameString`, commandes PowerShell/WMI non bloquantes (`Win32_VideoController`, `Win32_PhysicalMemory`, `Win32_DiskDrive`).
5. **macOS Desktop (`.dmg`, Apple Silicon & Intel)** :
   - *Spécificités* : Structure bundle `Bobine.app/Contents/Resources/`, LaunchAgent utilisateur, `caffeinate` pour la prévention de veille, décodage/encodage matériel VideoToolbox.
   - *Télémétrie/Matériel* : `sysctl -n machdep.cpu.brand_string`, `system_profiler SPDisplaysDataType / SPMemoryDataType`, `diskutil info /`, `ioreg -rc AppleSmartBattery`.

*Règle d'or de robustesse* : Toute fonction de détection système doit encapsuler ses appels d'OS dans des blocs `try/except` défensifs avec repli élégant (`None` ou étiquette par défaut). Le serveur backend ne doit JAMAIS lever une exception HTTP 500 sur un appel de télémétrie matérielle ou d'état.

### 1.3 Validation Systématique et Déterministe
Avant de déclarer toute tâche terminée ou de préparer un commit :
1. **Backend** :
   - Valider la syntaxe AST Python : `backend/.venv/bin/python -c "import ast; ast.parse(open('app/...').read())"` sur tout fichier modifié.
   - Exécuter la suite complète de tests : `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/` (les 56+ tests doivent tous être verts).
2. **Frontend** :
   - Contrôle strict du typage TypeScript : `npx tsc --noEmit` depuis `frontend/` (0 erreur tolérée).
   - Validation du build de production statique : `npm run build` depuis `frontend/`.
3. **Android** (si impacté) :
   - Compilation et signature : `ANDROID_KEYSTORE_PATH=... ./gradlew assembleRelease` depuis `android/`.
   - Vérification de la signature : `apksigner verify --verbose .../app-release.apk`.
4. **Validation sur Matériel Réel** :
   - **Wyse Headless** : Découverte DHCP dynamique si changement d'IP :
     ```bash
     SUBNET=$(ip route | grep default | awk '{print $3}' | cut -d. -f1-3).0/24
     nmap -p 8000 --open "$SUBNET" -oG - | grep "8000/open"
     ```
     Test rapide : `curl -s --connect-timeout 2 http://<WYSE_IP>:8000/api/settings`
     Accès direct : `ssh fanta@<WYSE_IP> "systemctl status bobine-backend bobine-kiosk"`
   - **Tablette Pilote Android** : Test ADB sans fil ou USB (`adb -s <TABLET_IP>:5555 ...`), déploiement `adb install -r`, et test en direct des endpoints (`/api/settings/system`, `/api/metrics/dashboard`).

### 1.4 Séquence de Démarrage pour une Nouvelle Session Sans Historique
Pour tout agent démarrant une session fraîche sans mémoire du dépôt :
1. **Vérifier l'état local Git** : `git status`.
2. **Résolution dynamique de l'IP Wyse** (adresse DHCP, peut changer) :
   - Étape A — Test de la dernière IP connue : `curl -s --connect-timeout 2 http://<WYSE_IP>:8000/api/settings`.
   - Étape B — Test via nom d'hôte mDNS : `curl -s --connect-timeout 2 http://<WYSE_HOSTNAME>.local:8000/api/settings`.
   - Étape C — Rescan réseau Nmap si l'IP a changé (cf. commande §1.3 ci-dessus).
   - Étape D — Confirmer l'IP trouvée avec un `curl` direct et l'utiliser pour les commandes SSH/API suivantes.
3. **Consulter l'état structuré du projet** : `.gemini/state.json` (non versionné, généré/maintenu localement).
4. Les valeurs réelles (hostnames, IP) de l'environnement du mainteneur sont dans `.agents/local-env.md` (non versionné) — voir §2.

---

## 2. Cartographie Spatiale (Environnements & Réseau)

| Environnement | Machine / Hostname | Adresse IP | Chemin du projet | Rôle / Services |
|---|---|---|---|---|
| **Développement Local** | `dev-machine.local` | `192.168.1.20` | `~/Developpement/web/Bobine` | Dev, tests unitaires, build Next.js |
| **Cible Production (Wyse)** | `bobine-appliance.local` (Dell Wyse 5070) | `192.168.1.30` (dernière connue) | `~/Bobine` | Kiosque Chromium (X11), Backend FastAPI (port 8000), Systemd services |
| **Tablette Pilote (Android)** | Tablette Android de test | `192.168.1.60` (Wi-Fi, ADB port variable) | `/data/data/com.bobine.app` | Double affichage tactile `/grid` + HDMI `/cinema`, FastAPI embarqué |

> Ces valeurs sont des exemples génériques. Voir **`.agents/local-env.md`** (non versionné) pour l'environnement de développement réel du mainteneur (hostnames et IP effectifs).

### Accès SSH Wyse
- Commande directe : `ssh fanta@<WYSE_IP>` (Authentification par clé SSH configurée sans mot de passe).

### Services Systemd (sur Wyse)
- `bobine-backend.service` — API Uvicorn (FastAPI)
- `bobine-kiosk.service` — Mode Kiosque Chromium
- `bobine-audio-guard.service` — Surveillance du système

---

## 3. Cartographie Temporelle & État du Projet

- **Branche Git actuelle** : `main` (branche propre, synchro `origin/main`).
- **Dernier Commit** : Version 3.0.5 Stable (Notes de release `docs/releases/V3.0.5.md`).
- **Fonctionnalités Clés** :
  - Kiosque d'affichage automatique avec reprise sur coupure et anti-veille Screen Wake Lock API.
  - Double canal de diffusion indépendant (*Câblé* et *Réseau*) + Canal Radio.
  - Multi-plateforme natif : Windows (`.exe`), macOS (`.dmg`), Linux Bureau (`.deb`), Appliance headless Wyse (`install.sh`), Android (`.apk`).
  - Sauvegarde & Restauration universelles (ZIP) et remise à zéro d'usine dans Réglages.
  - Console Régie Coach responsive (`/coach`) : console studio réactive avec disposition double colonne (pupitre audio, commandes tactiles 64px, minuteur et progression interpolés en temps réel, playlist déroulante intégrée, Stage Monitor 16:9 HDMI en direct et Palette tactile d'ambiances 1-clic) sur tablette paysage et desktop, et monoposte avec tiroirs tactiles rétractables sur mobile.
  - Hub d'Ambiances Visuelles (`/backgrounds`) : galerie 16:9 cinématique avec prévisualisations vidéo au survol, lecteur modal complet, projection 1-clic sur sorties Câblée/Réseau et fond par défaut coach.
  - Sélecteur visuel d'ambiance (`/audio`) : carte 16:9 interactive et galerie modale remplaçant le menu déroulant textuel pour les cours audio coach.
  - Redirection automatique `/dashboard-cable` vers `/coach` : dès que le mode coach est actif, toute navigation vers le tableau de bord câblé mène instantanément à la régie active pour synchroniser tous les écrans du personnel.
  - Projection d'ambiances directes hors séance sur les tableaux de bord Câblé et Réseau (`DashboardScreen`) avec carte de contrôle active et interruption 1-clic.
  - Persistance de `default_coach_background_id` dans `settings` et repli automatique dans l'orchestrateur de lecture audio.
  - Détection déterministe et extraction des durées des cours audio via `FFPROBE_BIN` sur tous les OS (y compris Android `libffprobe.so`) et rétro-migration automatique en base de données.
  - Enchaînement simplifié et sécurisé du mode coach : modes *Auto* et *Manuel* épurés, démarrage en pause par défaut, bouton « Quitter le mode coach » centré dans la structure, et synchronisation immédiate de la sortie câblée `/kiosk` sans F5.
  - Télécommande mobile et panneau d'admin Next.js (App Router).
  - Assistant d'installation & Télécommande Tauri (`assistant/`) pour piloter et déployer les bornes à distance.
  - Accélération matérielle multi-OS intégrale pour le réencodage (Full HW direct VRAM via VA-API, VideoToolbox, QuickSync, MediaCodec avec -94% de charge CPU et élimination du pic 30W, repli automatique hybride/logiciel) et support complet des vidéos lourdes (flux 4K 60 fps, 2K natif sans sous-échantillonnage avec débits adaptatifs jusqu'à 28 Mbps).
  - Mode « Race to Sleep » pour le réencodage vidéo (débridage des threads `-threads 0`, preset logiciel `ultrafast`, parallélisme `-async_depth 4`, copie directe flux AAC).
  - Mise à jour 1-clic multi-OS directement intégrée dans l'application (Linux `.deb`/git, Windows `.exe` silencieux, Android `.apk`).
  - Désinstallation complète 1-clic multi-plateforme (`/api/system/uninstall`) avec confirmation stricte et scripts de purge dédiés.
  - Descriptions et synopsis de cours : édition directe dans le volet Bibliothèque, affichage cinématique épuré sur l'écran de pause et dans les bannières cinéma/grille.
  - Qualité audio et vidéo réelle sur l'écran de pause : détection dynamique via ffprobe (`Mono 1.0`, `Stéréo 2.0`, `Surround 5.1`, `7.1`, résolutions 4K/2K/1080p/720p/SD) sans encombrement technique superflu.
  - Rétro-remplissage automatique des métadonnées étendues (fps, bitrate, canaux et codec audio, synopsis) lors de l'initialisation de la base de données.
  - Mode d'affichage hybride (`wired_display_mode` headless/dual_screen) et contrôle intelligent du capot d'ordinateur portable (mode Clamshell sans mise en veille via `gsettings`/`powercfg`).
  - Refonte UI/UX Grille Cinéma : widget Apple Glassmorphism sur le héros, suppression du voile fade-out brumeux, adoucissement des ombres des miniatures et réactivité instantanée du renommage des cours sans F5.
  - Notification « Nouvelle version disponible » aux couleurs du thème actif et cliquable vers les réglages.
  - Redesign complet des 16 thèmes d'interface (8 clairs, 8 sombres) avec noms en 1 mot, nuances chromatiques profondes et conformité stricte WCAG 2.1 AA/AAA.
  - Restructuration de la Documentation dans Paramètres (Accès Local 127.0.0.1 cliquable, Accès Réseau LAN/mDNS et Données/Stockage).
  - Suppression totale de l'animation d'introduction (`lancement.mp4`, -11 Mo sur les paquets et l'APK) et démarrage instantané de tous les cours sans latence.
  - Résolution de l'affichage HDMI headless Android (`/cinema` affiche la grille complète de cours en headless, et l'attente passive en mode double écran).
  - Audio direct sans délai : élimination des coupures et latences au lancement vidéo, initialisation explicite du son (`volume = 1.0`, `muted = false`, `preload="auto"`).
  - Support universel des contrôles (HTML5 Gamepad API pour manettes Xbox/PlayStation/Switch Pro/8BitDo, télécommandes multimédias physiques, souris, tactile) et relais des entrées sur la sortie HDMI externe Android (`BobinePresentation`).
  - Défilement horizontal fluide des titres longs (`MarqueeText`) avec masquage progressif et verrouillage strict des dimensions des miniatures (280px × 157.5px et 120px × 67.5px).
  - Élimination des saccades vidéo et de la boucle infinie Play/Pause (watchdog destructif 2,5s supprimé) et lissage strictement monotone du temps de lecture sur `/grid`.
  - Clarification du découplage de `/grid` (contrôle exclusif de la sortie câblée HDMI).
  - Métadonnées AppStream et licence AGPL-3.0 certifiées pour le Centre d'Applications Ubuntu (`bobine.metainfo.xml`).
  - Moteur Vidéo Gapless A/B Deck (`/cinema`) : double instance `<video>` en continu dans le DOM éliminant les écrans noirs de 200 à 600 ms entre cours.
  - Système de Notation 5 Étoiles : recueil d'avis à la fin de chaque séance sur `/grid` et `/cinema` (télécommande, manette, souris, tactile) avec auto-fermeture de 5 minutes.
  - Sessions d'assiduité (`playback_sessions`) et nouveau tableau de bord d'analytics `/metrics` (4 KPIs, histogramme horaire 24h CSS, classement des cours).
  - Supervision matérielle étendue : puissance instantanée en Watts (W), températures CPU/GPU (°C), modèles commerciaux des composants (CPU, GPU, Disque), télémétrie RAM détaillée (marque/constructeur, technologie LPDDR5X/DDR5/DDR4, fréquence max en MHz/MT/s) et Uptime/Runtime intégrés dans `/settings` et `/metrics`.
- **Fichier d'état structuré** : Consulte `.gemini/state.json` pour la représentation complète de l'état.

---

## 4. Guide des Commandes d'Exploitation Rapides

```bash
# Tester l'API Wyse à distance
curl -s http://<WYSE_IP>:8000/api/settings
curl -s http://<WYSE_IP>:8000/api/health

# État de lecture par canal (câblé / réseau)
curl -s "http://<WYSE_IP>:8000/api/playback/state?channel=cable"
curl -s "http://<WYSE_IP>:8000/api/playback/state?channel=network"

# Statut des services sur la Wyse via SSH
ssh fanta@<WYSE_IP> "systemctl status bobine-backend bobine-kiosk"

# Mettre à jour et redémarrer la Wyse
ssh fanta@<WYSE_IP> "cd /home/fanta/Bobine && git pull && sudo ./install.sh --skip-packages"
```

---

## 5. Canal de mise à jour (Stable / Bêta) & Cycle de release

> **RÈGLE ABSOLUE — ne jamais créer de tag `V*-beta.N`, `V*-rc.N` ou tout
> autre tag de pre-release par itération.** Le canal Bêta n'a qu'**un seul**
> tag, littéralement nommé `beta`, jamais renommé ni dupliqué. Publier une
> nouvelle bêta = force-déplacer CE tag sur le nouveau commit et republier
> PAR-DESSUS l'unique release existante (`gh release delete beta` puis
> `gh release create beta`, déjà automatisé par le job `release-beta` — ne
> jamais le faire à la main autrement). Si un jour un agent ou un humain
> retombe dans le réflexe "un tag par version bêta", la page GitHub Releases
> publique redevient illisible en quelques itérations — c'est exactement ce
> que ce modèle a remplacé (cf. historique : `V3.0.1-beta.1` a existé
> brièvement puis a été supprimé au profit de ce système).

- **Source de vérité de la version** : fichier `VERSION` à la racine du dépôt
  (ex. `3.0.5`, sans préfixe). Lu par `install.sh`, les scripts de packaging
  (`packaging/*/build_*.sh`, `bobine.iss`) et le backend
  (`app/utils/version.py`) — bumper CE fichier avant de taguer une release,
  jamais les ~8 endroits qui étaient codés en dur avant ce lot.
- **Deux canaux, structurellement séparés** :
  - **Stable** : un tag Git **strict** `Vx.y.z` (ex. `V3.0.5`, jamais de
    suffixe) par version, historique normal sur GitHub Releases. Le tag doit
    avoir la même base que `VERSION` — la CI (job `version`) refuse de
    publier sinon.
  - **Bêta** : PAS de tag par itération (les anciens `V3.0.1-beta.1`,
    `V3.0.1-beta.2`… ont été abandonnés — ça finissait par rendre la page
    Releases publique illisible). Un tag **unique et mobile**, `beta`,
    force-déplacé sur le commit publié à chaque déclenchement — une seule
    entrée "Bêta" sur GitHub, toujours à jour, jamais d'accumulation.
- **Publication (CI, `.github/workflows/ci.yml`)** :
  - Stable → pousser un tag `Vx.y.z` déclenche automatiquement le job
    `release-stable` (notes obligatoires dans `docs/releases/<TAG>.md`,
    sinon échec explicite — pas de repli silencieux).
  - Bêta → **automatique à chaque push direct sur `main`** (hors tag), ou
    déclenchement manuel (Actions → Run workflow → cocher *publish_beta* ;
    "Use workflow from" choisit la référence — utile pour republier sans
    nouveau commit) → job `release-beta` : force-déplace le tag `beta`,
    supprime puis republie l'unique release Bêta (`gh release delete beta`
    puis `gh release create beta`), notes de version **générées
    automatiquement** (changelog `git log <dernier tag stable>..HEAD`).
    Aucune action manuelle requise pour qu'un push sur `main` se retrouve en
    Bêta — corrigé le 8 sept. après un incident réel où la Bêta est restée
    6 commits en retard faute de republication manuelle.
  - Les deux publient les 4 artefacts (`.exe`, `.deb`, `.dmg`,
    `bobine-assistant`) + `install.sh`. Noms de fichiers Bêta **fixes**
    (`Bobine-Setup-beta.exe`, `Bobine-beta.dmg`, `bobine_beta_amd64.deb`) —
    jamais de `~` dedans (GitHub réécrit silencieusement `~` en `.` dans les
    noms d'assets téléchargés, découvert en pratique sur une première
    itération de ce système).
- **Mise en page des notes de la release Bêta** (étape "Generate rolling
  release notes" du job `release-beta`) : même structure visuelle que le
  README — bannière `Assets/Images/bobine_banner.svg`, titre, tableau de
  téléchargement avec les badges shields.io par plateforme (mêmes badges que
  le README, un lien direct par asset), puis le changelog dans un bloc de
  code (\`\`\`) pour un rendu lisible ligne par ligne. Générée dans un
  heredoc bash **entièrement quoté** (`<<'NOTES_EOF'`) pour que les
  backticks/badges markdown restent littéraux sans échappement — seuls
  `__COMMIT__`/`__VERSION__` sont substitués après coup par `sed` (le
  changelog, lui, est ajouté à part via `>>`, jamais par `sed`, un message
  de commit pouvant contenir des caractères qui casseraient une
  substitution). En modifiant ce bloc, préserver cette mise en page — ne
  jamais revenir à un simple texte brut.
- **Réglage `update_channel`** (`"stable"` | `"beta"`, défaut `"stable"`) :
  persisté dans la table `settings` comme `theme`/`language`, modifiable
  depuis Réglages → Mises à jour ("Programme Bobine Beta"). Consommé par
  `GET /api/updates/check` ([updates.py](backend/app/routers/updates.py)) :
  `stable` interroge `/releases/latest` (exclut structurellement les
  pre-releases côté API GitHub) et compare des numéros de version (semver) ;
  `beta` interroge `/releases/tags/beta` (tag fixe) et compare des **commits**
  (`target_commitish` vs le commit local, bundlé via `COMMIT` sur les profils
  packagés qui n'ont pas de `.git` — cf. `app/utils/version.py`), puisqu'il
  n'y a pas de numéro de version qui avance à chaque build sur ce canal.
- **`install.sh --channel stable|beta`** : sélectionne/persiste le canal
  (`/etc/bobine/update-channel`). Stable cherche le dernier tag `Vx.y.z`
  strict ; bêta vise directement le tag fixe `beta` (`git fetch --tags
  --force`, nécessaire pour suivre un tag mobile). L'assistant Tauri propose
  le même choix (étape Options du wizard) et le relaie via `--channel=...`.
- **Downgrade** : `apply_update()` du profil `linux-headless` (bouton
  "Mettre à jour" de Réglages) fait un `git checkout <tag>` — jamais un
  `git pull --ff-only` — ce qui permet de revenir sur un tag antérieur (ex.
  repasser d'une bêta à la dernière stable).
- **Promouvoir la Bêta en release officielle** : il n'y a pas de bouton
  "promouvoir" — la Bêta est un instantané de `main`, une Stable est un tag
  figé sur un commit précis. Le geste est simplement de couper une release
  normale à partir de ce même `main` :
  1. `VERSION` porte déjà la version visée par la Bêta courante — la bumper
     seulement si le contenu final dépasse ce qui était prévu.
  2. Écrire `docs/releases/V<version>.md` — orienté fonctionnalités/mise en
     valeur (contrairement aux notes Bêta, générées automatiquement).
  3. Committer `VERSION` + les notes, pousser sur `main`.
  4. `git tag V<version> && git push origin V<version>` — déclenche
     automatiquement `release-stable`, qui reconstruit des artefacts frais
     depuis ce commit exact et publie une release GitHub normale
     (`prerelease: false`), distincte de la Bêta (qui continue d'exister en
     parallèle sous son tag `beta`, pointant potentiellement déjà plus loin
     sur `main`).
- **Assistant Tauri — auto-conscience de version** (réf. mission "hiérarchie
  des versions") : `bobine-assistant` embarque désormais sa propre
  version/commit à la compilation (`assistant/src-tauri/build.rs`, commande
  `get_app_info`), lus depuis `VERSION`/`COMMIT` écrits par la CI juste
  avant `cargo build` — mêmes fichiers que ceux lus par le backend Python.
  Sans ça, un assistant construit depuis le canal Bêta (donc déjà plus
  récent) se voyait proposer une "mise à jour" vers la dernière Stable, en
  réalité PLUS ANCIENNE. `assistant/ui/app.js::compareVersions()` est un
  port JS du comparateur semver du backend (`_parse_version`) — à garder
  synchronisé si l'un des deux évolue.
- **Assistant Tauri — scan réseau complet & clé SSH importée** (réf. mission
  "scan réseau complet") : `scan_network` (`assistant/src-tauri/src/commands/discovery.rs`)
  retient un appareil dès qu'UN SEUL signal répond (SSH, Bobine, port usuel
  HTTP/HTTPS/Samba/RDP/AirPlay/impression, ou simple connexion refusée sur un
  port fermé) — plus seulement SSH/Bobine — et résout le nom d'hôte en DNS
  inverse. Toute valeur réseau non fiable (nom d'hôte...) DOIT être échappée
  avant `innerHTML` côté JS (`escapeHtml()` dans `app.js` — un appareil du LAN
  peut renvoyer n'importe quoi en PTR DNS). Les mocks de prévisualisation
  navigateur (`invokeTauri` dans `app.js`, quand `window.__TAURI__` est
  absent) utilisent volontairement des IP RFC 5737 (`203.0.113.0/24`, jamais
  une plage privée plausible) et affichent un bandeau d'avertissement
  permanent — ne jamais remettre des IP réalistes dans ces mocks, ça a été
  pris pour un vrai scan qui "invente" des appareils. `authenticate_session`
  (`ssh_auth.rs`) essaie désormais une clé importée explicitement (bouton
  "Importer une clé SSH", sélecteur de fichier `tauri-plugin-dialog`) EN
  PREMIER, avant mot de passe/agent/clés `~/.ssh/` usuelles.

### 5.1 Protocole Pas-à-Pas : Comment Incrémenter une Version de Bobine

L'incrémentation d'une version de Bobine (corrective, mineure ou majeure) touche l'ensemble des 5 profils d'exécution et les outils d'orchestration. Pour maintenir l'alignement absolu sans dérive :

1. **Source de Vérité Unique (`VERSION`)** :
   - Mettre à jour le fichier `VERSION` à la racine du dépôt : ex. `echo "3.1.0" > VERSION` (format semver strict, sans préfixe `V`, sans suffixe, sans espace ni saut de ligne superflu).
   - Ce fichier est la référence unique lue par l'ensemble des scripts de packaging (`build_deb.sh`, `build_dmg.sh`, `bobine.iss`), `install.sh`, l'Assistant Tauri et le backend Python.

2. **Backend Python (`app/utils/version.py`)** :
   - Aligner la constante de secours : `_FALLBACK_VERSION = "x.y.z"` dans `backend/app/utils/version.py`.
   - `get_app_version()` lit en priorité le fichier `VERSION` sur le disque (présent dans le dépôt ou embarqué par PyInstaller/Chaquopy). Le repli `_FALLBACK_VERSION` n'intervient que si le fichier physique est inaccessible.

3. **Application Android Native (`android/`)** :
   - Le build Gradle (`android/app/build.gradle.kts`) extrait dynamiquement `VERSION` pour `androidVersionName` et calcule `androidVersionCode` à partir du nombre de commits git (`git rev-list --count HEAD`).
   - La tâche Gradle `stagePythonSources` copie automatiquement `VERSION` et `COMMIT` dans `android/app/src/main/python/` afin que Chaquopy et le backend Python embarqué disposent des métadonnées au runtime.
   - Le service d'arrière-plan (`ForegroundService.kt`) et le gestionnaire de mise à jour (`UpdateManager.kt`) consomment directement `BuildConfig.VERSION_NAME` et `/api/updates/check`.
   - Pour recompiler et vérifier l'APK :
     ```bash
     cd android && ./gradlew assembleRelease
     apksigner verify --verbose app/build/outputs/apk/release/app-release.apk
     ```

4. **Assistant Tauri (`assistant/`)** :
   - `assistant/src-tauri/build.rs` lit `VERSION` et `COMMIT` à la compilation et génère le fichier embarqué consommé par la commande Tauri `get_app_info`.
   - Les comparaisons de version dans l'interface (`assistant/ui/app.js::compareVersions()`) utilisent le même algorithme semver que le backend.

5. **Notes de Version (`docs/releases/`)** :
   - **Pour une version Stable** (`Vx.y.z`) : Rédiger obligatoirement `docs/releases/Vx.y.z.md` mettant en valeur les fonctionnalités majeures, les optimisations de performance et les correctifs. Le workflow GitHub Actions échoue si ce fichier est absent lors du push du tag.
   - **Pour le canal Bêta** : Les notes sont générées automatiquement par la CI à partir du changelog git (`git log <dernier tag stable>..HEAD`).

6. **Validation Complète Multi-OS & Push** :
   - Exécuter la suite de validation systématique (§1.3) : AST Python, tests pytest (56+ tests), typage TypeScript (`npx tsc --noEmit`), build Next.js (`npm run build`).
   - Committer avec le format Conventional Commits : `chore(release): bump version to x.y.z` ou `feat(...): ...`.
   - Zéro mention d'IA, zéro balise `Co-authored-by`.
   - Pousser sur `main` :
     - Si Bêta : déclenchement automatique du job `release-beta` qui republie sur le tag mobile `beta`.
     - Si Stable : créer le tag strict `git tag Vx.y.z && git push origin Vx.y.z` pour déclencher `release-stable`.

- **Commandes rapides** :
  ```bash
  # Publier une nouvelle version stable
  echo "3.1.0" > VERSION
  # ... écrire docs/releases/V3.1.0.md ...
  git add VERSION docs/releases/V3.1.0.md && git commit -m "chore(release): 3.1.0"
  git push && git tag V3.1.0 && git push origin V3.1.0

  # Publier/rafraîchir la Bêta (depuis main, sans rien tagger à la main)
  gh workflow run ci.yml -f publish_beta=true

  # Vérifier le canal courant sur la Wyse
  ssh fanta@<WYSE_IP> "cat /etc/bobine/update-channel; curl -s http://127.0.0.1:8000/api/settings | grep update_channel"
  ```

---

## 6. Dépôt APT Debian/Ubuntu & Déploiement GitHub Pages (`apt.bobine.fit`)

- **Hébergement & CNAME** : Le site du dépôt APT et les métadonnées de paquets sont hébergés sur la branche `gh-pages` du dépôt principal `FantasmaGlad/Bobine` et servis sur `https://apt.bobine.fit` via Cloudflare (mode Full Strict, SSL/TLS 1.2+).
- **Clé Cryptographique GPG** :
  - Clé RSA 4096-bit générée pour `Bobine APT Repository <contact@bobine.fit>`.
  - Empreinte certifiée : `941B 6F52 6A72 59F4 694C F4BC 1B5D 18A9 76FA AD15`.
  - Clé publique exportée à la racine : `bobine.gpg` (téléchargeable directement pour `/etc/apt/keyrings/bobine.gpg`).
- **Canaux APT** :
  - `stable` : pointe vers les paquets de releases officielles taguées (ex: `bobine_3.0.0_amd64.deb`).
  - `beta` : pointe vers les builds du canal Bêta rolling.
- **Interconnectivité avec BobineWeb & Baamix** :
  - La documentation sur le site principal (`bobine.fit/fr/documentation/demarrage-rapide`) et la base de connaissances auto-générée de l'assistant Baamix (`src/app/api/chat/route.ts`) recommandent l'installation via `apt.bobine.fit` pour les machines de bureau Debian/Ubuntu/Mint.
  - Le fichier `public/llms.txt` de `bobine.fit` et `apt.bobine.fit` documentent les 3 commandes d'installation pour les moteurs génératifs (Perplexity, ChatGPT, Claude, Gemini).
- **Jeu Rétro Pong (`/pong/`) & Recrutement Linux** :
  - Jeu d'arcade rétro en HTML5 Canvas plein écran (100vh sans défilement, score géant, physique des rebonds angulaires, sons Web Audio 8-bit, zéro emoji).
  - Ancrage en bas à droite du footer invitant les passionnés de Linux à contribuer au projet (`clement.barillot3901@gmail.com`).
- **Indexation & Directives GEO** :
  - `robots.txt` autorise explicitement tous les robots d'indexation traditionnels et IA.
  - `sitemap.xml` déclare les routes multilingues `/`, `/fr/` et `/pong/`.
  - `llms.txt` fournit la spécification complète de l'archive APT pour les requêtes conversationnelles.
  - Balises OpenGraph, Twitter Cards et données JSON-LD Schema.org intégrées à chaque page.

---

## 7. Portabilité Android (`android/`) — chantier en cours

- **État au 2026-09-11 (Lot 15 — performance, stabilité réseau, thème)** :
  Cause racine principale des symptômes rapportés (sortie câblée
  intermittente, lenteur réseau généralisée, saccades câblées, kiosk réseau
  gelé/incontrôlable, bibliothèque incohérente) : la base SQLite et les
  miniatures/logs vivaient sur le stockage externe Android (FUSE, lent),
  bloquant la boucle d'évènements asyncio à chaque requête concurrente.
  Corrigé par une double racine de stockage (interne pour la base/logs/
  miniatures, externe pour les médias, migration automatique non
  destructive — validée sur émulateur avec des données réelles
  pré-existantes), des appels SQLAlchemy sortis du threadpool, une
  diffusion WebSocket parallélisée et un keepalive assoupli (20s→60s +
  pong proactif sur `visibilitychange`), un cache WebView revalidé au lieu
  de désactivé, et un évènement `library_change` temps réel. Thème
  **Charbon Sombre** ajouté (AA/AAA validé par calcul de contraste réel).
  Mission secondaire (installateur headless) traitée : paquets audio
  manquants (`alsa-utils`/`pipewire`/`wireplumber`), étapes `capabilities`
  et `tuning`. **Validé en conditions réelles sur la tablette pilote
  physique**, à la demande explicite de l'utilisateur : APK release signé
  avec le keystore de production (même certificat que l'installation
  existante, `adb install -r` propre, zéro perte de données). Bug critique
  supplémentaire trouvé PENDANT ce déploiement :
  `RevalidateStaticFiles` (`backend/app/main.py`) servait des pages HTML
  périmées après mise à jour sur TOUTES les plateformes (ETag non basé sur
  le contenu réel + repli `If-Modified-Since` cassé par le mtime figé du
  build reproductible) — cause racine directe du rapport "/grid n'affiche
  aucune vidéo". Corrigé, reconstruit, redéployé et reconfirmé sur le même
  appareil : `/grid` affiche désormais la vraie vidéo avec sa miniature.
- **Avant de toucher quoi que ce soit dans `android/`** : lire
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (§1 « Portabilité Android »
  et §10 « Matrice des interfaces ») — ce document détaille l'architecture
  retenue pour l'application Android. Note : plusieurs commentaires dans le
  code (`backend/app/`, `android/`) référencent encore un fichier
  `docs/plan-implementation-android.md` (plan détaillé par lots) qui
  n'existe plus dans `docs/` — voir la note de suivi en fin de section.
- **État au 2026-09-09 (fin de session)** : Lots 0, 2, 3, 4, 5, 6, 7 et 13
  exécutés. 0/2/3/4/5/6/7 validés sur **émulateur Android réel** (KVM, AVD
  `Medium_Phone` x86_64 API 37, déjà configuré sur cette machine — `adb
  devices` pour vérifier s'il tourne encore, sinon
  `~/Android/Sdk/emulator/emulator -avd Medium_Phone -no-window -no-audio
  -no-boot-anim` pour le relancer) : double affichage indépendant
  `/kiosk` (`127.0.0.2`) + `/cinema` (`127.0.0.1`) simultané, WebSocket,
  `ForegroundService` survivant à la fermeture de l'app (`dumpsys`), verrou
  mDNS. APK release signé avec une clé dédiée (§ci-dessous), build/CI
  opérationnels, `versionCode`/`versionName` désormais dynamiques (injectés
  par la CI, plus de constante figée — pré-requis du Lot 11).
  **Première installation réelle sur la tablette pilote faite le 2026-09-09**
  (Xiaomi Pad 8, HyperOS/Android 16, `adb` USB — activer "Installation via
  USB" dans les Options développeur si `INSTALL_FAILED_USER_RESTRICTED`) :
  a révélé deux bugs invisibles sur émulateur, tous deux corrigés — icône de
  lanceur absente (ajoutée, adaptive icon), et `ERR_CLEARTEXT_NOT_PERMITTED`
  bloquant totalement les WebView (corrigé par
  `android/app/src/main/res/xml/network_security_config.xml`, cleartext
  autorisé uniquement vers `127.0.0.1`/`127.0.0.2`). Voir Découvertes du
  Lot 1 dans le plan pour le détail complet, y compris un blocage réseau non
  résolu (mDNS résout `bobine.local` mais le port 8000 est filtré depuis un
  autre appareil du même Wi-Fi — probablement pare-feu HyperOS ou isolation
  client du routeur, pas un bug Bobine). Lots 8-10 et 12 restent à faire ;
  Lot 1 formellement pas clos (dock/HDMI physique pas encore testé). Le bug
  frontend d'hydratation React sur `/kiosk` (`task_67d56a94`) se reproduit
  identiquement sur le vrai matériel mais reste non bloquant (la page
  s'affiche quand même) — toujours traité séparément, ne pas retoucher
  `useDisplayOutputRedirect.ts` pour Android sans vérifier l'état de cette
  tâche.
- **Clé de signature release** : générée hors dépôt, dans
  `~/.bobine-signing/` sur la machine du mainteneur (jamais commitée — voir
  son `README.md` pour la procédure de sauvegarde, **critique**, et les
  commandes `gh secret set`). Les 4 secrets GitHub Actions correspondants
  sont déjà configurés sur le dépôt.
- **CI** : job `android-build` dans `.github/workflows/ci.yml`, build+signe
  à chaque push. **Décision actée : ne publie PAS sur les releases
  Stable/Bêta publiques** tant que le portage n'est pas prêt pour de vrais
  utilisateurs (Lots 4-12 manquants) — reste un artefact CI téléchargeable
  depuis l'onglet Actions. Ne pas câbler ce job dans les `needs:` de
  `release-stable`/`release-beta` sans re-décider explicitement ce point.
- **Structure** : `android/` à la racine, en miroir de `backend/`/
  `frontend/`/`assistant/`. Projet Gradle/Kotlin avec le plugin Chaquopy
  (CPython embarqué) — `android/gradlew` est **committé** (wrapper Gradle
  9.7.1) pour un build reproductible sans installer Gradle manuellement ;
  nécessite `ANDROID_HOME` pointant vers un SDK Android (platform 36+,
  aucun NDK requis — Chaquopy fournit ses bibliothèques natives
  pré-compilées) et un JDK 17.
- **`backend/app/` n'est pas copié tel quel dans l'APK** — une tâche Gradle
  (`stagePythonSources`/`buildFrontendStatic` dans `android/app/build.gradle.kts`)
  met en scène uniquement `backend/app/` (pas `.venv/`/`data/`/`tests/`) et
  le frontend compilé, dans une disposition spécifique imposée par la
  structure fixe des assets Chaquopy (`AssetFinder/app/`) — voir les
  Découvertes du Lot 2 avant d'y toucher, ce n'est pas une simple copie.
  Trois modules de compatibilité Pydantic v1 existent uniquement pour ce
  profil : `backend/app/utils/_pydantic_compat.py`,
  `backend/app/utils/_polling_observer.py` (repli `watchdog`), et des
  `try/except ImportError` disséminés dans `backend/app/` (v1 downgrade,
  cf. CDC §3.1/§10 pour la voie de retour vers Pydantic v2).
- **Tablette pilote** : Xiaomi Pad 8 (édition développeur), Android 16 —
  utilisée pour la première fois le 2026-09-09 en USB/adb (voir État
  ci-dessus) ; reste à tester avec le dock USB-C + écran HDMI physique
  (Lot 1/Lot 4).
- **Suite du 2026-09-09 (même journée, session prolongée)** : Lots 9 et 12
  avancés, Lot 8 bloqué sur un vrai mur de sécurité Android (pas un bug de
  code) :
  - **Lot 9** : `_data_root()` (`backend/app/config.py`) gère désormais
    Android explicitement (`getExternalFilesDir` via
    `BOBINE_ANDROID_DATA_DIR`, posé par `BobineForegroundService.kt` →
    `bobine_bootstrap.py`) — avant ce fix, les données utilisateur
    (vidéos, `database.db`) vivaient par accident dans `AssetFinder/app/`,
    le dossier où Chaquopy redéploie les SOURCES de l'app à chaque mise à
    jour. Validé sur émulateur.
  - **Lot 12** : `get_deployment_profile()`/`get_profile_handler()`
    gèrent un profil `"android"` explicite (nouveau
    `deployment_profiles/android.py`) — avant, retombait par accident sur
    `"linux-desktop"`. `restart_services()` fait `os._exit(0)` comme les
    autres profils mais **non testé en conditions réelles** (aucun bouton
    reset/restore déclenché pour de vrai) ; pas de superviseur dédié côté
    Android, seul `START_STICKY` peut relancer le `Service`.
  - **Lot 8 (ffmpeg) : bloqué, mur de sécurité Android identifié, PAS un
    problème de code.** Deux découvertes : (1) empaqueter en
    `jniLibs/<abi>/lib*.so` ne suffit pas seul — il faut aussi
    `packaging.jniLibs.useLegacyPackaging = true` dans
    `android/app/build.gradle.kts`, sinon le binaire reste compressé dans
    l'APK et `nativeLibraryDir` reste vide (fait, validé). (2) **Une fois
    ça corrigé, tout binaire statique générique glibc testé
    (johnvansickle.com) meurt avec `SIGSYS` dès qu'il est exécuté en
    subprocess DEPUIS l'app** — fonctionne pourtant parfaitement via
    `adb shell` direct. C'est le filtre seccomp-bpf spécifique aux
    process app Android (plus restrictif que le shell) qui tue le
    process sur un appel système que ce binaire desktop générique
    déclenche au démarrage. Pistes non explorées : build musl (runtime
    plus minimal, syscall problématique peut-être absent), ou compilation
    NDK native (solution robuste mais lourde). L'infrastructure de
    résolution de chemin (`backend/app/utils/ffmpeg_binaries.py`) est
    prête et correcte, indépendamment du binaire final retenu.
  - Détail complet dans l'historique des Lots 8/9/12.
- **Suite du 2026-09-09 (session prolongée, 3ᵉ vague)** : Lots 10 et 11
  avancés, cause racine du Lot 8 identifiée avec certitude :
  - **Lot 10 (Device Owner)** : `BobineDeviceAdminReceiver` (aucune
    politique, `<uses-policies />` vide) + exemption batterie via le
    mécanisme standard `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`
    (PAS une capacité silencieuse de Device Owner — aucune API DPM
    publique documentée pour ça). Provisionné avec succès sur émulateur
    (`dpm set-device-owner`, sans wipe nécessaire tant qu'aucun compte
    Google n'est configuré). **Découverte utile** : Device Owner bloque
    bien `adb uninstall`/`dpm remove-active-admin`
    (`DELETE_FAILED_DEVICE_POLICY_MANAGER`) — pour retester proprement
    depuis zéro sur émulateur, seul un `-wipe-data` complet fonctionne.
    Reste à faire sur la tablette pilote : test de survie 24h, et
    vérifier si HyperOS/MIUI (connu pour sa propre gestion batterie
    hors-AOSP, cf. dontkillmyapp.com) respecte cette exemption ou exige
    un réglage manuel supplémentaire (Sécurité → Batterie → Bobine →
    Aucune restriction).
  - **Lot 11 (mise à jour in-app)** : `UpdateManager.kt` réutilise
    l'endpoint backend existant `/api/updates/check` (pas d'appel direct
    à l'API GitHub depuis Kotlin) ; si un `.apk` direct existe un jour
    (`routers/updates.py` a maintenant `.apk` comme `target_ext` pour le
    profil `android`, inerte tant que Lot 13 ne publie rien), télécharge
    et déclenche l'installation via `FileProvider` + `ACTION_VIEW`.
    Validé : la vérification fonctionne réellement (profil détecté,
    comparaison de version correcte). **Non testable** : téléchargement
    et installation réels, faute d'un `.apk` public existant — ce
    morceau restera non vérifié tant que la décision du Lot 13
    (publication différée) n'est pas révisée.
  - **Lot 8 (ffmpeg) : cause racine trouvée avec certitude via
    diagnostic approfondi** (endpoints de debug temporaires, retirés) :
    ce n'est PAS un syscall spécifique à un codec, c'est **le runtime de
    démarrage glibc statique lui-même** que le filtre seccomp des
    process app Android tue avant même `main()`. Preuve décisive : un
    `busybox` statique **musl** (busybox.net) exécuté pareil (subprocess
    depuis l'app) fonctionne sans problème, alors que tout binaire
    statique **glibc** testé (peu importe la version, de 2019 à 2026)
    meurt par `SIGSYS`. **Prochaine étape nette pour qui reprend ce
    lot** : chercher/construire un ffmpeg statique **musl** ARM64
    (aucune source prête identifiée — BtbN et martin-riedl.de sont
    dynamiques, johnvansickle.com est glibc ; pistes : toolchain
    `musl.cc` portable + build minimal, ou compilation NDK native).
- **Suite du 2026-09-09 (4ᵉ vague, tablette pilote branchée à un vrai dock
  + écran externe) : révision d'architecture actée + Lot 1/4 validés pour
  de vrai sur matériel.**
  - **Révision demandée par l'utilisateur, appliquée** : l'écran tactile
    de la tablette (`MainActivity.kt`) charge désormais `/cinema` sur
    `127.0.0.1` (même canal câblé que la `Presentation` HDMI) au lieu de
    `/kiosk` sur `127.0.0.2` (canal réseau indépendant). L'écran tactile
    doit être la grille de sélection des cours vidéo ; l'écran externe
    branché comme un vidéoprojecteur diffuse le cours sélectionné — les
    deux `WebView` sont sur le même canal, synchronisées (backend déjà
    multi-client par canal, rien à changer côté Python). Constante
    renommée `KIOSK_URL` → `CINEMA_URL`. `/kiosk`/`127.0.0.2` restent
    disponibles si besoin futur, juste plus utilisés par défaut.
  - **Lot 1 (dock/HDMI physique) et Lot 4 (double affichage) validés
    pour de vrai** avec un vrai dock USB-C + écran externe (« Wisecoco »,
    2560×1600) : `DisplayDeviceInfo{"Écran HDMI"...}` bien créé par le
    framework, `Presentation` attachée **sans race condition, du premier
    coup** (meilleur que le pire cas de l'émulateur, 15 réessais parfois
    nécessaires). Piège découvert : la boîte de dialogue HyperOS
    « Dupliquer l'écran ? » au branchement **n'a aucun rapport** avec le
    fonctionnement réel de `DisplayManager`/`Presentation` de l'app — un
    choix par défaut du launcher pour son propre contenu, à ignorer pour
    diagnostiquer le vrai état (utiliser `adb shell dumpsys display` /
    `dumpsys SurfaceFlinger --display-id`, pas l'apparence de ce dialogue).
    Accès à la tablette maintenu via **ADB sans fil** (`adb connect
    <ip>:<port>`) quand le port USB-C est occupé par le dock — pratique
    à refaire dans une session future si besoin.
- **Suite du 2026-09-09 (5ᵉ et 6ᵉ vagues, fin de session) : Lot 14 validé,
  ergonomie de diffusion, thème charbon AAA, netteté 1080p et seek temps réel** :
  - **Tablette pilote Wi-Fi** : IP dynamique de la tablette pilote passée sur
    une nouvelle adresse locale (précédemment Ethernet, puis dev local) —
    valeur réelle non pertinente ici (DHCP), cf. `.agents/local-env.md`.
  - **Écran HDMI veille sobre** : remplacement de la duplication de la
    grille par un écran d'attente sobre "En attente d'un cours" avec horloge
    et pulsation douce.
  - **Thème "charbon" minéral clair** : contraste conforme WCAG AA/AAA sur
    toutes les interfaces (fond minéral `#e8ecef`, cartes blanches `#ffffff`,
    texte `#161a1d`, accent `#0a58ca`), synchronisation périodique robuste.
  - **Lot 8 clos (Binaires Bionic ARM64)** : compilation NDK r28c
    (`libffmpeg.so` / `libffprobe.so`), 16 KB page-size compatible Android
    15+, zéro `SIGSYS`, repli miniature manuelle conservé universellement.
  - **Résolution du flou des miniatures** : passage du gabarit de réduction
    Pillow de 640×360 à 1920×1080 (`Image.Resampling.LANCZOS`, `quality=92`,
    `optimize=True`) dans `videos.py` et `importer.py`. Suppression de
    `transform: scale(1.03)` sur `.cinema-hero-backdrop` et ajout de
    `image-rendering: -webkit-optimize-contrast` sur `.card-thumbnail` et
    le fond héros. Rendu cristallin sur écran 2.8K et TV 4K.
  - **Élimination du roll back lors du seek** :
    - `/cinema` : verrouillage des rapports WebSocket et d'`onTimeUpdate`
      pendant `el.seeking`, évitant la fuite de positions intermédiaires
      obsolètes pendant le calage d'image clé du décodeur.
    - `/grid` : intégration d'un état `optimisticSeek` avec libération
      automatique dès confirmation réseau ou 1.2s max, assurant une
      réactivité instantanée et permettant les taps consécutifs (+10s, +10s).
    - Support tactile universel : gestionnaires `onTouchEnd` ajoutés sur les
      curseurs de navigation temporelle (`/cinema`, `/grid`, `DashboardScreen`).
- **Suite du 2026-09-09 (7ᵉ vague) : plein écran `/grid` sans sidebar, accélération matérielle multi-OS, annulation réactive FFmpeg et support des vidéos lourdes 4K 60 fps** :
  - **Plein écran `/grid` sans sidebar** : `/grid` et `/grid/` ajoutés à
    `isFullscreenRoute` dans `frontend/src/components/ClientLayout.tsx`. L'écran
    tactile bénéficie désormais d'un affichage autonome 100% dédié sans barre
    d'administration desktop polluante.
  - **Accélération matérielle multi-OS (`video_utils.py`)** :
    - Android : `h264_mediacodec` avec options d'accélération `-operating_rate 1000 -pix_fmt nv12`
      (gain mesuré : passage de 3.0x à 4.2x / 5.1x temps réel, CPU réduit de 28%).
      Décodage matériel `av1_mediacodec` automatique avec repli dynamique si source AV1.
    - macOS : `h264_videotoolbox` natif (Apple Silicon M1 à M4 et puces Intel).
    - Linux / Wyse : `h264_vaapi` via `/dev/dri/renderD128` (QuickSync/Mesa) avec
      paquet `intel-media-va-driver` ajouté à `install.sh`.
    - Windows : `h264_qsv` (Intel QuickSync), tenté en premier puis repli libx264
      sur échec — corrigé le 2026-09-11, ce profil n'avait AUCUNE accélération
      matérielle jusque-là (gap trouvé lors d'un audit multi-plateforme).
    - Repli universel logiciel transparent sur `libx264 -preset veryfast` si GPU indisponible.
  - **Support des vidéos lourdes et haute cadence (4K 60 fps, zéro sous-échantillonnage)** :
    - Aucune mise à l'échelle destructive (`scale=...`) sur les résolutions 2K ou 4K.
    - Calcul adaptatif de débit cible haute fidélité (`_get_target_bitrate`) :
      4K UHD à 28 Mbps (max 35M), 2K QHD à 14 Mbps (max 18M), 1080p FHD à 6 Mbps (max 8M), 720p HD à 3.5 Mbps.
  - **Annulation réactive des importations (Croix ✕)** :
    - Registre de processus et de futures dans `backend/app/utils/import_jobs.py`
      (`register_job_process`, `cancel_job`, `JobCancelledError`).
    - Endpoint `DELETE /api/import-jobs/{job_id}` qui stoppe immédiatement le
      processus FFmpeg (`SIGTERM`/`SIGKILL`), annule le Future et déclenche le
      nettoyage des fichiers temporaires/partiels sans laisser d'orphelin ni insérer
      en base.
    - Câblé dans `UploadManager.tsx` côté frontend : interruption XHR ou requête DELETE API.
  - **Télémétrie en temps réel (ETA)** :
    - Lecture non-bloquante de `stderr` de FFmpeg via un thread d'arrière-plan pour
      prévenir tout interblocage de buffer, et capture de `-progress pipe:1`.
    - Calcul continu de la vitesse (`speed`), de l'ETA en secondes (`eta_seconds`)
      et du pourcentage (`progress_percent`), affichés dans le badge de progression.
  - **Validation sur matériel réel** : testé et validé avec succès sur la tablette
    pilote (Wi-Fi). Annulation à 83.6% vérifiée, nettoyage des résidus confirmé,
    zéro orphelin. Tests unitaires backend à 39/39 et vérification TypeScript
    frontend 100% propre.
- **Suite du 2026-09-10 (8ᵉ vague) : Élimination du freeze vidéo au seek (Chrome Android), vitrine /cinema réseau et imports atomiques** :
  - **Élimination du freeze d'image au seek sous Chrome Android** :
    - *Cause racine* : désynchronisation audio/vidéo MediaCodec lors d'un seek à chaud (l'audio redémarrait immédiatement, laissant le décodeur vidéo en retard sur le GOP) et écrasement en boucle du tampon par `position_tick` (toutes les 250 ms) pendant que `video.seeking` était actif.
    - *Correctif (`kiosk/page.tsx`, `cinema/page.tsx`)* : suspension temporaire de la lecture dans `seekWhenReady` avant l'assignation de `currentTime`, reprise conditionnée à l'évènement `seeked` (avec timeout de secours), garde anti-réentrance `if (el.seeking) return`, période de grâce de 3s ignorant les ticks sur les kiosques miroirs, et watchdog `requestVideoFrameCallback` pour détecter le gel réel d'affichage vidéo (`presentedFrames`).
  - **Vitrine `/cinema` déverrouillée pour les clients réseau** :
    - *Cause racine* : `isAndroidHdmiScreen = true` était appliqué aveuglément dès que `deployment_profile === "android"`, masquant la vitrine aux navigateurs connectés au LAN.
    - *Correctif (`cinema/page.tsx`)* : conditionné strictement à `deployment_profile === "android" && isWiredDisplay()`.
  - **Imports atomiques et conformité HTTP Range** :
    - *Imports atomiques (`importer.py`)* : normalisation via fichier temporaire `temp_norm_*` puis déplacement atomique `shutil.move` vers `final_dest_path`, purge immédiate des fichiers tronqués en bloc `finally`.
    - *Streaming HTTP Range (`main.py`)* : support des plages suffixées (`bytes=-N`) et suppression de l'en-tête `Content-Range` lors des réponses HTTP 200 complètes (RFC 7233 / 9110).

- **Statut de version (mis à jour au 2026-09-13)** : dernier tag stable réel
  publié : `V3.0.5` (`VERSION` à jour, notes `docs/releases/V3.0.5.md`
  publiées sur GitHub Releases). Les notes `docs/releases/V3.0.3.md` et
  `docs/releases/V3.0.4.md` existent bien toutes les deux et séparément dans
  `docs/releases/` (une note précédente affirmant que `V3.0.4.md` avait été
  fusionnée dans `V3.0.3.md` puis supprimée était devenue fausse — les deux
  versions ont finalement été publiées séparément ; ne pas se fier à cet
  historique pour l'état réel, se référer uniquement à `VERSION` et
  `docs/releases/` sur le disque).
- **Renforcement réseaux imparfaits (2026-09-11)** : `position_tick` porte un `tick_seq` croissant par canal (`playback_manager.py`) ; le client détecte un écart et resynchronise immédiatement via REST (`usePlaybackSocket.ts`, `doResyncRef`) au lieu d'attendre le cycle de 15s.

> **Note de suivi documentaire** : plusieurs commentaires dans le code
> source (`backend/app/`, `android/`, `frontend/src/`) référencent des
> fichiers `docs/plan-implementation-android.md`,
> `docs/plan-implementation-portabilite-crossplatformx.md` et
> `docs/PortabiliteAndroid.md`/`docs/audit-android-2026-09-11.md` qui
> n'existent plus dans `docs/` à ce jour (probablement renommés/fusionnés
> dans `docs/ARCHITECTURE.md` et `docs/cahier-des-charges-v3.0.5.md` à un
> moment donné sans que les références en commentaire soient mises à jour).
> Ce nettoyage est hors périmètre de ce document (fusion `AGENTS.md`
> uniquement) — à traiter séparément dans le code source concerné.
