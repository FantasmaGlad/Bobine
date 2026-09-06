# Cahier des charges — Portage multi-OS de Bobine

Statut : proposition / à valider. Fait suite à l'audit de portabilité
Windows/macOS du 2026-09-05 (analyse statique du dépôt, sept angles
d'audit indépendants). Complète `docs/cahier-des-charges-installeur.md`,
qu'il ne remplace pas : l'assistant Tauri qui y est décrit reste le
chemin d'installation de **l'appliance Linux headless** (§3). Ce document
couvre les **trois nouvelles cibles** — Windows, Linux de bureau, macOS —
et le préalable architectural qui les rend possibles.

**Lot 0 (§4) implémenté le 2026-09-06** — détail complet, vérification et
découvertes faites en cours de route dans
[`plan-implementation-portabilite-crossplatformx.md`](plan-implementation-portabilite-crossplatformx.md)
§1.4. Point notable : la persistance de l'état après un crash-restart (§4.2
ci-dessous) s'est révélée sans régression réelle, pas seulement « sans
migration de données » comme formulé initialement.

**Lot 1 (§5) implémenté le 2026-09-06** — conforme à ce qui est décrit
ci-dessous (PyInstaller deux exécutables, Inno Setup, `pystray`,
`zeroconf`, chemins `%ProgramData%`, pare-feu, avertissement SmartScreen
documenté). Détail, vérifications réalisables sans machine Windows et
découvertes de packaging dans
[`plan-implementation-portabilite-crossplatformx.md`](plan-implementation-portabilite-crossplatformx.md) §2.

**Lot 2 (§6) implémenté le 2026-09-06** — conforme à ce qui est décrit
ci-dessous (paquet Debian `.deb` via `dpkg-deb`, deux exécutables PyInstaller
autonomes dans `/usr/lib/bobine/`, wrapper `/usr/bin/bobine`, intégration XDG
`bobine.desktop` autostart et `~/.local/share/bobine/`, service systemd user,
`BobineTray` avec anti-veille X11 et détection multi-navigateurs, job CI `linux-desktop-deb`).
Détail complet dans
[`plan-implementation-portabilite-crossplatformx.md`](plan-implementation-portabilite-crossplatformx.md) §3.

**Lot 3 (§7) implémenté le 2026-09-06** — `pystray` retenu (pas `rumps`),
bundle `.app` via `BUNDLE()`, chemins `~/Library/Application Support/Bobine`,
`caffeinate` pour l'anti-veille kiosque, `.dmg` via `hdiutil`, job CI
`macos-build`. Deux écarts assumés par rapport à la rédaction initiale
ci-dessous, expliqués en détail dans le plan §4 : le LaunchAgent est
auto-installé par `BobineTray` à son premier lancement plutôt que posé par
un script d'installeur (un `.dmg` glisser-déposer n'a pas de hook
`postinstall`), et le répondeur mDNS embarqué reste actif sur macOS
(Bonjour natif ne publie pas spécifiquement `bobine.local`, seulement le
nom de la machine). Détail complet et découvertes de packaging dans
[`plan-implementation-portabilite-crossplatformx.md`](plan-implementation-portabilite-crossplatformx.md) §4.

## 1. Objectif

Faire de Bobine une application installable nativement sur quatre
familles de systèmes, dans cet ordre de priorité :

1. **Windows, via un installeur `.exe` complet** — support natif intégral.
   Explicitement écarté : toute solution reposant sur WSL2 comme
   moteur d'exécution. Le backend, ffmpeg et l'ensemble de la pile
   tournent nativement sous Windows, sans virtualisation Linux
   intermédiaire.
2. **Linux non-headless (nouveau)**, avec un support privilégié pour
   **Debian et dérivés** (paquet `.deb`) — et, en continuité,
   clarification de ce qui distingue ce profil de l'appliance headless
   actuelle (§3).
3. **macOS**, avec un installeur natif (`.pkg`/`.dmg`).

Le changement de fond n'est pas seulement technique : jusqu'ici, Bobine
n'avait qu'un seul profil de déploiement (l'appliance de salle de sport,
sans tête, verrouillée). Ce CDC en introduit un second — l'**application
de bureau grand public** — et les deux coexistent (§3), sans que le
second ne remplace le premier.

## 2. Résumé des arbitrages actés

Les choix suivants ont été tranchés avec le porteur du projet le
2026-09-05 et ne sont plus à rediscuter dans le cadre de ce CDC ; ils
sont repris tels quels dans les sections qui suivent.

| # | Sujet | Décision |
|---|---|---|
| 1 | Mode d'affichage (Windows/macOS/Linux desktop) | **App de bureau par défaut** (fenêtre/icône, lancement manuel) ; le mode kiosque plein écran devient une **option**, pas une obligation. |
| 2 | Périmètre de l'assistant Tauri | **Reste dédié au SSH vers Linux headless** (cf. `cahier-des-charges-installeur.md`). Les trois nouvelles cibles reçoivent des installeurs natifs séparés (`.exe`, `.deb`, `.pkg`/`.dmg`), pas une extension de `assistant/core`. L'interface Tauri reprendra fidèlement le style et le design system du logiciel Bobine. |
| 3 | Redis | **Supprimé sur les quatre cibles** (y compris l'appliance Linux headless actuelle). Bascule en mono-process, état partagé en mémoire — voir §4. |
| 4 | HDMI-CEC | **Aucun développement.** Le README (FR/EN, lignes 38 et 205) est corrigé : l'extinction TV repose sur la veille automatique native du téléviseur en absence de signal HDMI, pas sur une commande CEC émise par Bobine. |
| 5 | Point d'entrée « app de bureau » | **Icône de barre système/menu bar + navigateur par défaut.** Pas de coquille applicative native (pas de webview dédiée) à construire pour l'admin/le kiosque. |
| 6 | Compatibilité ascendante | **Aucune contrainte de migration.** Changement de version majeure assumé — pas d'installation en production à préserver. |
| 7 | Signature de code | **Non budgétée pour l'instant.** Les installeurs Windows/macOS restent non signés ; l'avertissement SmartScreen/Gatekeeper et sa procédure de contournement sont documentés pour l'utilisateur (§9.2). |
| 8 | Windows : nature du support | **Support natif complet**, explicitement pas une surcouche WSL2 — confirmé indépendamment de la décision #1. |

## 3. Deux familles de déploiement, clairement distinguées

C'est la clarification demandée en tête de ce CDC. Bobine devient deux
produits packagés différemment à partir de la **même base de code
applicative** (backend Python, frontend Next.js) :

| | **Appliance headless** (existant, inchangé) | **App de bureau** (nouveau, 3 cibles) |
|---|---|---|
| Cibles | Debian 13 sans bureau, mini PC dédié | Windows, macOS, Linux avec bureau |
| Installeur | `install.sh` piloté par l'assistant Tauri en SSH distant (`cahier-des-charges-installeur.md`) | Installeur natif local (`.exe`, `.deb`, `.pkg`/`.dmg`) |
| Mode d'affichage | Kiosque X11 plein écran **obligatoire** | Fenêtre/onglet navigateur par défaut, kiosque **optionnel** |
| Supervision | `systemd` système (root), `Restart=always`, watchdog timer | Lancement au login utilisateur + icône barre système, pas de service système |
| Public visé | Exploitant de salle de sport, matériel dédié | Utilisateur individuel installant sur son propre PC/Mac |
| Élévation de privilèges | `sudo`/`su -`, sudoers restreint (`install.sh:1266-1294`) | UAC (Windows) / admin ponctuel (macOS) au moment de l'installation seulement |

Les deux familles partagent : le backend FastAPI, le frontend Next.js
exporté statiquement, SQLite, ffmpeg, et — après le Lot 0 (§4) —
l'absence totale de Redis et de multi-worker. Seule la **couche
packaging + autostart + supervision** diffère par cible.

### 3.1 Le modèle administrateur + sorties (câblé/réseau/radio) est inchangé
dans les deux familles — précision apportée le 2026-09-06

Point à ne pas confondre avec le mode d'affichage (décision #1) : le
**workflow applicatif** de Bobine repose sur une séparation entre

- une **URL administrateur** unique, consultable indifféremment au format
  téléphone ou PC (responsive), qui sert à **contrôler** les trois canaux
  de diffusion — câblé, réseau, et radio (planning, bibliothèque,
  télécommande, réglages) ;
- des **écrans dédiés aux sorties** — un par canal (câblé, réseau, radio),
  chacun affichant le contenu effectivement diffusé sur ce canal.

Cette séparation **ne dépend pas** du profil de déploiement et **ne
change pas** avec le passage au mode app de bureau. La décision #1
(kiosque optionnel) porte uniquement sur la question « le navigateur qui
affiche une sortie est-il verrouillé en plein écran ou non » — elle ne
supprime ni ne redéfinit l'administrateur, qui **existe toujours** comme
interface de contrôle distincte des sorties, y compris sur les profils
Windows/macOS/Linux bureau. Un utilisateur qui installe l'app de bureau
retrouve exactement le même modèle : il ouvre l'administrateur (depuis son
PC ou son téléphone, sur le même réseau local) pour piloter ses sorties
câblé/réseau/radio, que ces sorties soient affichées sur des fenêtres/
onglets de son propre PC ou sur d'autres appareils du foyer.

Conséquence pratique : le mécanisme existant de connexion au téléphone
(ouvrir l'URL de l'administrateur depuis le réseau local — déjà affichée
dans Réglages, cf. `network.local_ip`/`network.mdns_url`) **couvre déjà**
le cas d'usage « connecter mon téléphone depuis le salon » pour les trois
nouvelles cibles, au même titre que pour l'appliance headless. Il n'y a
**pas** de nouveau parcours d'interface à concevoir pour ce point — voir
la correction correspondante dans
`plan-implementation-portabilite-crossplatformx.md` §6.

## 4. Préalable architectural — Lot 0 : suppression de Redis et du multi-worker

C'est le chantier qui conditionne tous les autres (décision #3). Il
s'applique aux **quatre cibles**, y compris l'appliance Linux headless
actuelle, et doit être livré et validé **en premier**, sur
l'environnement de référence actuel (Debian headless), avant tout
travail spécifique à Windows/macOS/Linux-bureau.

### 4.1 Ce qui change

- `uvicorn app.main:app --workers 4` → `--workers 1` (`install.sh:939`).
  Un seul process élimine par construction le besoin de coordination
  inter-process : Redis n'était utile **que** pour ça.
- Bus pub/sub WebSocket inter-workers (`ws_manager.py:249,298-300,305`)
  → diffusion directe en mémoire (une liste de connexions actives dans
  le même process, plus de canal Redis).
- Synchronisation planning inter-workers (`scheduler_manager.py:682,714,
  737-739`) → état partagé directement en mémoire (plus besoin de
  publier/writer un état que d'autres workers doivent relire).
- Verrou global ffmpeg (`video_utils.py:45-66`) → `asyncio.Lock()` ou
  `threading.Lock()` local, plus de `redis.lock()`.
- Verrou de dé-duplication de tick (`tick_lock.py`, `SET NX PX`) →
  dictionnaire en mémoire avec timestamp d'expiration.
- File de jobs d'import (`import_jobs.py`) → file en mémoire
  (`asyncio.Queue` ou équivalent), le comportement observable ne change
  pas pour l'utilisateur.
- `install.sh` : suppression du paquet `redis-server`, de
  `After=network.target redis-server.service` / `Wants=redis-server.service`
  dans `bobine-backend.service` (`install.sh:669,674-678,931-932`).

### 4.2 Ce qui NE change PAS

- SQLite reste l'unique stockage persistant (`data/database.db`) — Redis
  ne portait **aucune donnée persistante**, uniquement de l'état
  transitoire (bus pub/sub, verrous). **Aucune migration de données
  n'est nécessaire** pour ce chantier : c'est un point de confort
  important compte tenu de la décision #6.
- Les routes FastAPI, les modèles SQLAlchemy, les appels ffmpeg restent
  identiques.

### 4.3 Point de vigilance à valider

Le passage à un seul worker réduit la capacité de traitement concurrent
du backend. Pour l'usage réel de Bobine (un kiosque, un écran réseau,
quelques télécommandes mobiles, un admin) c'est a priori largement
suffisant, mais ce point doit être **validé par un test de charge
réaliste** avant de considérer le Lot 0 terminé — en particulier le
nombre de connexions WebSocket simultanées (kiosque + écran réseau +
remote mobile + admin ouvert) et le comportement de l'upload/import
vidéo pendant que le kiosque diffuse.

### 4.4 Critère de sortie du Lot 0

Le Lot 0 est terminé quand l'appliance Linux headless actuelle tourne,
sans Redis, avec un seul worker, sans régression fonctionnelle
observable (scheduling, radio, kiosque, télécommande, mise à jour de
la bibliothèque) — **avant** de démarrer les Lots 1 à 3.

## 5. Cible n°1 (priorité) — Windows natif, `.exe`

### 5.1 Fabrication de l'exécutable

Le backend Python doit être distribué sans exiger que l'utilisateur
installe Python lui-même. Recommandation : **PyInstaller** (le plus
répandu et documenté pour ce cas d'usage) pour figer :

- `BobineBackend.exe` — le backend FastAPI + ses dépendances Python.
- `BobineTray.exe` — le petit contrôleur de barre système (§5.3), qui
  démarre/surveille/arrête `BobineBackend.exe`.

ffmpeg (`ffmpeg.exe`/`ffprobe.exe`, builds statiques gyan.dev ou BtbN)
est embarqué tel quel à côté — les appels du backend sont déjà par nom
nu (`"ffmpeg"`, jamais de chemin Linux en dur), donc aucune adaptation
de code n'est nécessaire pour cet appel, seul le binaire change.

### 5.2 Installeur

Recommandation : **Inno Setup** (gratuit, produit un `.exe` unique,
suffisant pour ce périmètre — pas besoin du formalisme MSI/WiX pour une
app grand public sans déploiement d'entreprise). L'installeur :

- copie `BobineBackend.exe`, `BobineTray.exe`, `ffmpeg.exe`/`ffprobe.exe`,
  le dossier `frontend/out/` déjà construit par la CI, et un
  `config.toml` par défaut vers `%ProgramFiles%\Bobine\` ;
- crée les données applicatives (base SQLite, médias importés) sous
  `%ProgramData%\Bobine\` (cf. correctif de `backend/app/config.py:90`,
  déjà identifié dans l'audit — remplacer le littéral POSIX
  `/etc/bobine/config.toml` par une résolution consciente de la
  plateforme) ;
- pose un raccourci de démarrage (`shell:startup`, par utilisateur) qui
  lance `BobineTray.exe` à l'ouverture de session ;
- s'enregistre dans « Applications et fonctionnalités » avec un
  désinstalleur généré par Inno Setup (remplace l'enveloppe
  `sudo`/`systemd-run` actuelle, sans objet sur Windows).

### 5.3 Barre système et supervision (décision #5)

`BobineTray.exe` (ex. via `pystray` + `Pillow`, bibliothèque Python pure
qui fonctionne aussi sur Linux/macOS — cf. §6 et §7) affiche une icône
avec un menu : État (en ligne/hors ligne), Ouvrir l'administration
(ouvre `http://localhost:8000` dans le navigateur par défaut), Ouvrir en
mode kiosque (§5.4), Redémarrer, Quitter. Il surveille le process
`BobineBackend.exe` et le relance s'il meurt — équivalent applicatif du
`Restart=always` systemd, mais à l'échelle d'une app de bureau, pas d'un
service système. **Aucun Service Windows n'est nécessaire** pour ce
profil (à la différence de ce que l'audit envisageait pour un mode
« boîte noire » — non pertinent ici puisque le mode par défaut est une
app de bureau lancée par un utilisateur connecté, décision #1).

### 5.4 Mode kiosque (optionnel, décision #1)

Un item de menu « Ouvrir en mode kiosque » lance le navigateur par
défaut (ou Edge explicitement) avec
`--kiosk --autoplay-policy=no-user-gesture-required http://localhost:8000/kiosk`.
L'anti-veille (`SetThreadExecutionState(ES_CONTINUOUS|ES_DISPLAY_REQUIRED)`)
n'est activé **que pendant** cette session kiosque, jamais globalement —
contrairement à l'appliance headless, l'utilisateur qui installe Bobine
sur son PC personnel veut probablement garder son comportement de veille
habituel le reste du temps.

### 5.5 Découverte réseau (mDNS)

Windows n'a pas de répondeur mDNS actif par défaut. Plutôt que de
dépendre d'une installation séparée de Bonjour Print Services,
embarquer un répondeur mDNS **dans le process backend lui-même** (lib
Python `zeroconf`) publiant `bobine.local` — best-effort, non bloquant
si l'annonce échoue (l'admin reste accessible via `localhost`).

### 5.6 Signature de code (décision #7)

Non budgétée pour l'instant : documenter dans l'écran de fin
d'installation et sur le site que Windows affichera un avertissement
SmartScreen « Éditeur non reconnu », avec la marche à suivre (« Plus
d'informations » → « Exécuter quand même »). Point à revisiter si le
projet gagne une base d'utilisateurs justifiant le coût récurrent du
certificat.

### 5.7 Explicitement écarté

- Redis sous Windows (Memurai, WSL2 ou portage communautaire) — sans
  objet une fois le Lot 0 livré.
- WSL2 comme moteur d'exécution — exclu (décision #8).
- Assigned Access / mode kiosque Windows IoT — reste documenté comme
  option future si un profil « appliance Windows IoT » émergeait un
  jour, mais **hors périmètre** de ce CDC (le profil app de bureau ne
  le requiert pas).

## 6. Cible n°2 — Linux non-headless (nouveau)

### 6.1 Distinction avec l'appliance headless

Ce profil cible un utilisateur avec un **bureau graphique déjà présent**
(GNOME sur Debian/Ubuntu en priorité — cf. décision de support privilégié
Debian et dérivés) qui installe Bobine comme une application de bureau
classique, pas un exploitant qui provisionne un mini PC nu. Il **ne
remplace pas** `install.sh`/l'assistant Tauri (§3), qui reste le chemin
pour l'appliance headless.

### 6.2 Paquet

Un paquet **`.deb`** (via `dpkg-deb`/`debhelper`, ou l'outil `fpm` pour
aller plus vite) contenant :

- le backend Python et ses dépendances (soit un venv embarqué, soit des
  dépendances système déclarées — à trancher en implémentation, cf. §12) ;
- `frontend/out/` pré-construit ;
- une unité **systemd utilisateur** (`~/.config/systemd/user/bobine.service`,
  `systemctl --user enable --now bobine`), et non une unité système comme
  l'appliance — cohérent avec le profil « par utilisateur, pas root » de
  ce mode.
- un fichier `.desktop` pour l'icône de lancement + intégration au menu
  d'applications.

### 6.3 Barre système et kiosque

Même logique que Windows (§5.3, §5.4) via `pystray` (backend GTK/AppIndicator
sous Linux) : icône dans la zone de notification, menu identique, mode
kiosque optionnel via Chromium/Firefox `--kiosk`. `xset`/anti-veille
appliqué uniquement pendant la session kiosque, pas globalement.

### 6.4 mDNS

`avahi-daemon` est déjà présent nativement sur la plupart des
environnements de bureau Debian/Ubuntu — s'appuyer dessus s'il est actif,
sinon retomber sur le même répondeur `zeroconf` embarqué que Windows/macOS
pour ne pas dépendre d'un paquet système supplémentaire.

## 7. Cible n°3 — macOS (plus tard)

### 7.1 Paquet

Un bundle `.app` (via PyInstaller `BUNDLE()`) livré dans un `.dmg`
glisser-déposer vers `/Applications`. Autostart par utilisateur via un
**LaunchAgent** (`~/Library/LaunchAgents/`, pas un LaunchDaemon système —
même logique « par utilisateur » que Linux desktop) — **auto-installé par
`BobineTray` lui-même à son tout premier lancement** plutôt que posé par
un script d'installeur : un `.dmg` glisser-déposer n'a pas de hook
`postinstall` (contrairement à `install.sh`/`postinst` du `.deb`), et
l'alternative d'un `.pkg` avec script `postinstall` root pose son propre
problème (pas de `$HOME` fiable pour l'utilisateur graphique connecté).
Implémentation et vérifications :
[`plan-implementation-portabilite-crossplatformx.md`](plan-implementation-portabilite-crossplatformx.md) §4.

### 7.2 Barre menu

`pystray` (backend `_darwin`, AppKit/`NSStatusItem` via `pyobjc` — **pas
`rumps`**, écarté après vérification : dernière publication PyPI en 2022,
et son adoption forkerait la logique du tray au lieu de la partager entre
les 3 OS) pour l'icône de menu bar, même menu logique que Windows/Linux.
Mode kiosque optionnel via Chrome lancé par `open -na` (les navigateurs
sont des bundles `.app`, pas des exécutables nus sur le PATH) +
`caffeinate -d -i -w <pid>` attaché après coup au PID du navigateur,
pendant la session kiosque uniquement.

### 7.3 mDNS

**Pas gratuit, à nuancer** : Bonjour (`mDNSResponder`) est bien actif
nativement sur macOS, mais il publie le nom d'hôte *configuré de la
machine* (ex. « Mac-de-Jean.local »), pas spécifiquement `bobine.local`.
Le répondeur `zeroconf` embarqué (déjà utilisé pour Windows, §5.5) reste
donc actif sur ce profil aussi, pour la même raison — voir la découverte
documentée dans le plan §4.

### 7.4 Signature et notarisation (décision #7)

Non budgétée pour l'instant : documenter l'avertissement Gatekeeper
(« développeur non identifié ») et la procédure de contournement
(clic droit → Ouvrir, ou autorisation dans Réglages Système →
Confidentialité et sécurité). Revisiter si le budget Apple Developer
Program (~99 USD/an) est débloqué.

## 8. Ce qui ne change pas : l'appliance Linux headless

À réaffirmer explicitement pour ne pas le perdre de vue dans
l'excitation du multi-OS : le modèle actuel (Debian 13 sans bureau,
`install.sh`, systemd système, kiosque X11 **obligatoire**, assistant
Tauri en SSH distant) reste le chemin de référence pour l'usage salle de
sport. Il bénéficie du Lot 0 (§4, suppression de Redis) mais n'est
touché par **aucune** des sections 5 à 7. Un exploitant de salle de sport
qui installe Bobine aujourd'hui via `install.sh` continue de le faire de
la même façon demain.

## 9. Hors périmètre de ce CDC

### 9.1 HDMI-CEC (décision #4)

Correction documentaire à faire **indépendamment** du reste de ce CDC,
dès que possible : retirer ou reformuler la mention « gestion HDMI-CEC
automatisée » dans `README.md:38,205` et `README.fr.md:38,205`, en
précisant que l'extinction de la TV repose sur sa veille automatique
native en absence de signal HDMI (comportement déjà réel aujourd'hui,
sans code dédié).

Si cette fonctionnalité est un jour souhaitée malgré tout : elle exige
un **adaptateur USB-CEC dédié** (la plupart des GPU Intel/AMD de mini PC
n'exposent pas de transmetteur CEC sur leur sortie HDMI, à la différence
d'un Raspberry Pi) associé à **libCEC** (bibliothèque LGPL, builds
Linux/Windows/macOS), avec un module d'intégration backend analogue aux
appels ffmpeg existants. Coût matériel de l'ordre de 30 à 50 € par
poste, plus un développement et des tests de compatibilité TV multi-
marques (Anynet+/SimpLink/Bravia Sync se comportent différemment sous
un même protocole CEC). À chiffrer comme un chantier séparé si la
décision est reconsidérée.

### 9.2 Signature de code / notarisation (décision #7)

Documentée comme limitation assumée dans ce CDC (§5.6, §7.4), pas
développée davantage ici.

## 10. Compatibilité ascendante (décision #6)

Aucune contrainte de migration : ce CDC introduit un changement de
version majeure. Recommandation pratique malgré tout : marquer cette
livraison comme une version majeure clairement identifiée (changelog,
numéro de version) plutôt que de la fondre silencieusement dans une
mise à jour mineure, pour que quiconque suit le projet comprenne qu'il
s'agit d'un changement d'architecture (suppression de Redis,
introduction du profil app de bureau) et non d'un correctif.

## 11. Livrables et jalons

- **Lot 0 — Refonte mono-process** (§4) : suppression de Redis et du
  multi-worker, validée sur l'appliance Linux headless actuelle avant
  toute chose. Bloquant pour tous les lots suivants.
- **Lot 1 — Windows natif** (§5) : PyInstaller + Inno Setup, tray +
  supervision, kiosque optionnel, mDNS embarqué. Première cible livrée.
- **Lot 2 — Linux non-headless** (§6) : paquet `.deb`, service systemd
  utilisateur, tray Linux — réutilise directement le code du Lot 0/1,
  seule la couche paquet/service change.
- **Lot 3 — macOS** (§7) : bundle `.app`/`.dmg`, LaunchAgent, tray menu
  bar.
- **Lot transverse — Correction README HDMI-CEC** (§9.1) : indépendant
  des lots ci-dessus, à traiter dès que possible.
- **Lot optionnel, plus tard — Signature de code** (§9.2) : si budget
  débloqué, certificat Windows + Apple Developer Program/notarisation.

## 12. Questions ouvertes (à trancher en implémentation)

- Outil de « freeze » Python → exécutable : **PyInstaller** recommandé
  (le plus documenté) ; alternatives Nuitka/cx_Freeze à évaluer si des
  limites apparaissent (taille du binaire, faux positifs antivirus sur
  l'`.exe` généré — fréquents avec PyInstaller, à anticiper).
- Bibliothèque de barre système : **`pystray`** recommandé (un seul code
  pour les trois OS) vs trois implémentations natives séparées si
  `pystray` s'avère limitant sur un OS donné.
- Environnements de bureau Linux à tester en priorité : proposition
  Debian 12/13 + Ubuntu LTS récent, environnement GNOME par défaut — à
  confirmer.
- Port par défaut en mode app de bureau : garder `8000` comme
  aujourd'hui, ou choisir un port différent pour réduire le risque de
  conflit avec d'autres logiciels déjà installés sur la machine de
  l'utilisateur ?
- Mécanisme de mise à jour de l'app de bureau (retélécharger
  l'installeur manuellement vs auto-update intégré) : non cadré par ce
  CDC, à spécifier séparément si souhaité.
- Empaquetage des dépendances Python du `.deb` (§6.2) : venv embarqué
  dans le paquet vs dépendances système déclarées — impacte la taille
  du paquet et la facilité de mise à jour.
