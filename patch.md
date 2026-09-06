# Notes de version & Correctifs (patch.md)

Ce document consigne les évolutions, correctifs et améliorations UI/UX apportés à **Bobine**, dans la continuité des spécifications techniques du projet.

---

## 1. Stabilisation de l'affichage TV & Kiosk (`/kiosk`, `/cinema`)

### Problème résolu
- Sur les écrans TV et moniteurs à ratios non standards ou carrés (tels que 1600×1200, 4:3, 16:10), l'écran d'attente présentait des éléments étirés, distordus ou dispersés aux extrémités de l'écran en raison d'un ancien positionnement par pourcentages absolus hérité du moteur Canvas.
- Le logo et les textes de l'écran d'attente ne s'adaptaient pas harmonieusement aux dimensions réelles de la zone visible.

### Modifications techniques
- **Layout centré et fluide (`frontend/src/app/kiosk/page.tsx`)** :
  - Remplacement de la structure `kiosk-waiting-stage` et de ses cellules à coordonnées absolues par un conteneur Flexbox centré `kiosk-waiting-content`.
  - Hiérarchie verticale épurée : horloge grand format, logo central, prochain cours et compte à rebours.
- **Règles CSS adaptatives (`frontend/src/app/globals.css`)** :
  - Utilisation d'unités `vmin` et de fonctions `clamp()` pour l'horloge (`clamp(3.5rem, 8.5vmin, 7.5rem)`), le logo et les libellés.
  - Encadrement strict du logo (`.kiosk-waiting-stage-logo`) avec `object-fit: contain`, `max-height: clamp(80px, 20vmin, 180px)` et `max-width: min(65vw, 680px)`.
  - Maintien du ratio d'aspect originel du logo sans aucune déformation ni distorsion, quelle que soit la résolution du téléviseur ou du diffuseur vidéo.

---

## 2. Image de marque & Gestion du logo personnalisé (`/settings`)

### Problème résolu
- Dans la page Paramètres, la vignette de prévisualisation du logo débordait de sa boîte carrée de 72×72 px lorsque le logo était large.
- L'import d'un logo écrasait immédiatement l'affichage, sans permettre de basculer manuellement entre le logo officiel Bobine et le logo personnalisé sans supprimer ce dernier.

### Modifications techniques
- **Backend (`backend/app/routers/settings.py`)** :
  - Ajout du réglage `active_logo` (`"default"` ou `"custom"`) persisté en base de données SQLite (table `settings`).
  - Validation stricte dans `update_settings` : interdiction d'activer `"custom"` si aucun fichier logo personnalisé n'est présent sur le serveur.
  - Lors d'un téléversement (`POST /api/settings/logo`), le logo personnalisé est enregistré et immédiatement défini comme actif (`active_logo = "custom"`).
  - Lors d'une suppression (`DELETE /api/settings/logo`), le fichier est purgé du disque et le réglage repasse sur `"default"`.
  - Diffusion temps réel via WebSocket (`settings_change`) incluant `has_custom_logo` et `active_logo`.
- **Composant Logo (`frontend/src/components/AppLogo.tsx`)** :
  - Consommation de `activeLogo` : affichage du logo customisé uniquement si `activeLogo === "custom"` ET `hasCustomLogo === true`.
  - Protection CSS inline et par classe (`max-width: 100%`, `max-height: 100%`, `object-fit: contain`) pour garantir le confinement parfait dans tout conteneur parent.
- **Contexte d'application (`frontend/src/lib/AppSettingsContext.tsx`)** :
  - Exposition de `activeLogo` et de la méthode `setActiveLogo(choice)`.
  - Synchronisation instantanée locale et persistée vers l'API.
- **Interface Paramètres (`frontend/src/app/settings/page.tsx`)** :
  - Cadre de prévisualisation dimensionné (180×84 px) avec padding interne et fond surélevé (`--bg-surface-elevated`).
  - Ajout d'un sélecteur interactif segmenté (Boutons *Logo Bobine* / *Logo personnalisé*) dès qu'un logo est importé.
  - Bouton de remplacement du logo et bouton de suppression définitive avec confirmation modale.
  - Remplacement de la simple case à cocher par un bouton toggle segmenté explicite **Oui / Non** pour l'animation vidéo de lancement mp4 (`Lancement.mp4`) avant les cours en canal Câblé.

---

## 3. Harmonisation UI/UX du Design System & Nouveaux Thèmes

### Problème résolu
- Les thèmes existants présentaient des contrastes bruts (fonds vifs saturés, décalages de luminance entre surfaces).
- Manque de thèmes clairs chaleureux et équilibrés pour les salles de sport et studios lumineux.

### Modifications techniques
- **Harmonisation des thèmes existants (`frontend/src/app/globals.css`)** :
  - Vérification et renforcement des contrastes typographiques (respect des critères WCAG AA/AAA).
  - Adoucissement des fonds clairs (remplacement des aplats fluo par des teintes pastel feutrées pour `menthe`, `ciel`, `lavande`).
  - Enrichissement des fonds sombres (`lune`, `automne`, `hiver`, `chili`, `orchidee`, `taupe`, `charbon`) avec des élévations de surface subtiles et des bordures nettes.
- **Création de deux nouveaux thèmes clairs** :
  1. **Miel (`miel`)** :
     - Ambiance chaleureuse, dorée et lumineuse.
     - Fond crème ambré (`#fdfbf5`), surfaces blanches et ivoire (`#ffffff`, `#fef7e7`), typographie brun chaud (`#2b1d0c`, `#785723`), accent ambre doré (`#d97706`).
  2. **Coco (`coco`)** :
     - Ambiance naturelle inspirée de la noix de coco (lait de coco, crème douce et marron chocolat).
     - Fond blanc cassé velouté (`#faf7f4`), surfaces crème douce (`#ffffff`, `#f4ece5`), typographie chocolat torréfié (`#2a1c14`, `#6b4d3b`), accent bois noble / chocolat chaud (`#78350f`).
- **Enregistrement et internationalisation** :
  - Ajout des clés dans `_VALID_THEMES` (`backend/app/routers/settings.py`).
  - Ajout dans `Theme` et `THEME_VALUES` (`frontend/src/lib/AppSettingsContext.tsx`).
  - Traductions FR / EN dans `frontend/src/lib/i18n.ts`.
  - Pastilles de prévisualisation coordonnées dans `THEME_SWATCHES` (`frontend/src/app/settings/page.tsx`).
- **Classification des thèmes en deux catégories distinctes (`frontend/src/app/settings/page.tsx`)** :
  - Séparation visuelle nette dans les Paramètres entre **Thèmes clairs** (`clair`, `miel`, `coco`, `menthe`, `ciel`, `beige`, `lavande`) et **Thèmes sombres** (`les-mills-sombre`, `lune`, `automne`, `hiver`, `chili`, `orchidee`, `taupe`, `charbon`), avec en-têtes et icônes thématiques.
- **Thématisation dynamique des encadrés d'état sur l'écran principal (`frontend/src/app/globals.css`, `DashboardScreen.tsx`)** :
  - Remplacement des teintes vertes hardcodées par les variables du thème (`var(--accent-primary)`, `var(--bg-surface-elevated)`).
  - Les encadrés "En attente" (`.status-pill.waiting`), "Voir le planning" (`a.status-pill`) et les statuts système s'adaptent désormais instantanément au thème actif (doré en Miel, chocolat chaud en Coco, indigo en Lune, rouge Les Mills en Sombre/Clair, sauge en Menthe, etc.).

---

## 4. Documentation & Référencement (`README.md`, `README.fr.md`)

- Repositionnement discret des listes de mots-clés SEO en fin de document (section pied de page) pour préserver la lisibilité humaine et l'élégance de la présentation tout en maintenant l'indexation.

---

## 5. Suivi des Releases & Découplage des Paramètres de Transition

### Modifications techniques
- **Découplage des sections de configuration (`frontend/src/app/settings/page.tsx`)** :
  - Séparation nette entre la section **Animation de lancement** (vidéo `Lancement.mp4` pour canal Câblé avec commutateur Oui / Non) et la section **Durées de transition & Mode Coach** (durée d'attente entre cours de playlist, minuteur enchaînement coach, fondu des rappels radio et volume).
- **Module de suivi des mises à jour (`backend/app/routers/updates.py`, `backend/app/main.py`)** :
  - Endpoint `GET /api/updates/check` : compare la version locale Git / tag (`git describe`, `git rev-parse`) avec la dernière release officielle de `FantasmaGlad/Bobine` via l'API GitHub.
  - Tolérance réseau complète : en mode hors-ligne ou sans connexion Internet, la réponse est traitée de manière gracieuse sans blocage ni erreur serveur.
  - Endpoint `POST /api/updates/apply` : déclenche la mise à jour asynchrone et la relance des services.
- **Interface & Animation professionnelle (`frontend/src/app/settings/page.tsx`, `frontend/src/app/globals.css`)** :
  - Bouton interactif « Rechercher une mise à jour » avec animation de rotation fluide (`.olc-spin`).
  - Affichage de la version actuelle et du commit actif.
  - Badge « Système à jour » ou notification détaillée avec notes de version dépliables et bouton d'installation directe.

---

## 6. Mission PortabiliteCrossPlatformX — Lot 0 : suppression de Redis, backend mono-processus

### Contexte
Premier lot d'un chantier de portabilité multi-OS (Windows, Linux de bureau, macOS) détaillé dans [`docs/cahier-des-charges-multi-os.md`](docs/cahier-des-charges-multi-os.md) et [`docs/plan-implementation-portabilite-crossplatformx.md`](docs/plan-implementation-portabilite-crossplatformx.md). Ce lot est un préalable architectural bloquant pour les lots suivants (voir ces documents pour le détail complet).

### Impact site web / releases
- **Aucun impact utilisateur ni sur le site bobine.fit** : changement d'architecture interne, aucune fonctionnalité visible n'est ajoutée ou retirée.
- **À mentionner dans les notes de la prochaine release GitHub** : suppression de la dépendance à Redis (utile pour quiconque aurait scripté une supervision externe autour de `redis-server` sur son installation).

### Modifications techniques (résumé — détail dans le CDC §4)
- Backend passé de 4 workers `uvicorn` à 1 seul (`install.sh`, `bobine-backend.service`) : l'état de lecture (câblé/réseau/radio), les verrous de tick et de planning, la file d'import et le bail « kiosque primaire » vivent désormais entièrement en mémoire d'un seul processus, sans bus d'état externe.
- Suppression complète de la dépendance `redis` (`backend/requirements.txt`, `install.sh`, `scripts/watchdog.sh`).
- `backend/app/utils/redis_client.py` et `tick_lock.py` supprimés ; `boot_state.py` simplifié (identifiant de démarrage local au processus, sans lecture `/proc`).
- `GET /api/health` ne rapporte plus de composant « redis ».
- Aucune migration de données : Redis ne portait que de l'état transitoire, jamais de données persistantes (SQLite reste l'unique stockage).
- Documentation corrigée en conséquence : `README.md`/`README.fr.md`, `docs/ARCHITECTURE.md`, `docs/cahier-des-charges-radio.md`, contexte des agents IA (`.agents/`, `.gemini/`).

---

## 7. Mission PortabiliteCrossPlatformX — Lot 1 : application de bureau Windows native (`.exe`)

### Contexte
Deuxième lot du chantier de portabilité multi-OS, priorité n°1 du CDC : Bobine s'installe désormais aussi comme une application de bureau Windows classique (PC ou mini PC Windows 10/11/IoT), en plus de l'appliance headless Debian existante. Détail complet dans [`docs/cahier-des-charges-multi-os.md`](docs/cahier-des-charges-multi-os.md) et [`docs/plan-implementation-portabilite-crossplatformx.md`](docs/plan-implementation-portabilite-crossplatformx.md) §2.

### Impact site web / releases
- **Nouveau livrable de release GitHub** : chaque release doit désormais joindre `Bobine-Setup-<version>.exe` (produit par le job CI `windows-build`), en plus des artefacts existants.
- **À mentionner dans les notes de release** : premier support Windows natif ; avertissement SmartScreen « éditeur non reconnu » à documenter comme limitation connue (pas de signature de code pour l'instant, CDC décision #7).
- Nouvelle section README (FR/EN) « Installer sur Windows » — à référencer depuis le site bobine.fit une fois celui-ci mis à jour.

### Modifications techniques (résumé — détail dans le plan §2)
- Module partagé `backend/app/utils/deployment.py` + `backend/app/utils/deployment_profiles/` : détection de profil (`linux-headless`/`windows`, `linux-desktop`/`macos` réservés aux lots suivants) et abstraction `ProfileHandler` pour éviter toute collision future sur `settings.py`/`updates.py`/le frontend.
- `backend/app/desktop/tray.py` : icône de zone de notification (`pystray`), supervision du process `BobineBackend` (relance sur mort ou échec répété de `/api/health`), lancement du mode kiosque optionnel (Edge `--kiosk` ou navigateur par défaut).
- `backend/app/utils/mdns.py` : le backend publie lui-même `bobine.local` (`zeroconf`), remplace l'annonce Avahi de l'appliance headless.
- `backend/app/config.py` : données applicatives sous `%ProgramData%\Bobine` (et non `%ProgramFiles%`, non inscriptible sans élévation) ; chemins et exécutable figé (`sys.frozen`) résolus dynamiquement.
- Endpoints de réinitialisation/désinstallation (`routers/settings.py`) et de mise à jour (`routers/updates.py`) adaptés par profil ; mise à jour Git désactivée sur ce profil (réinstallation du `.exe` à la place) ; page Paramètres du frontend adaptée en conséquence.
- Packaging : `packaging/windows/{bobine.spec,bobine.iss,bobine.ico}` (PyInstaller + Inno Setup, FR/EN, licence AGPL-3.0 affichée, règle de pare-feu automatique pour la télécommande mobile) ; nouveau job CI `windows-build`.
- **Non vérifiable dans cet environnement de développement Linux** : compilation réelle par Inno Setup, exécution du `.exe` sur une vraie machine Windows, avertissement SmartScreen, invite pare-feu, autostart à l'ouverture de session — écrit d'après la documentation officielle, à valider au premier passage du job CI et lors d'un test manuel sur machine Windows réelle avant toute distribution publique (détail dans le plan §2).
