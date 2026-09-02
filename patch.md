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
