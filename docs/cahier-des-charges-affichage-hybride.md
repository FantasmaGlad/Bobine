# Cahier des charges — Mode d'Affichage Hybride (Pupitre Studio vs Headless)

> Spécification fonctionnelle et technique définitive pour le basculement dynamique entre le mode **Double Écran (Pupitre Studio `/grid` + HDMI `/cinema`)** et le mode **Écran Unique (Headless)** sur Ordinateurs Portables et Tablettes Android.

---

## 1. Contexte & Objectifs

Bobine dispose aujourd'hui de deux paradigmes d'affichage distincts :
1. **Le modèle Headless (Appliance fixe / Mini PC Wyse 5070)** :
   L'appareil n'a pas d'écran propre. La sortie HDMI diffuse directement la vitrine automatique (`/kiosk`) ou le cinéma libre-service (`/cinema`), piloté à distance par télécommande mobile (`/mobile`) ou par écran tactile HDMI.
2. **Le modèle Double Écran Tactile (Tablette Android Xiaomi Pad 8 - Lot 14)** :
   L'écran tactile intégré de la tablette affiche la grille de sélection autonome (`/grid`) avec son widget de régie, tandis que la sortie HDMI externe diffuse la vidéo plein écran épurée (`/cinema`) sans commandes superposées.

### Objectifs validés
Permettre à l'utilisateur de **choisir et basculer facilement** entre ces deux modes depuis l'interface d'administration (Paramètres) :
- **Sur PC Portable (Laptop)** :
  - **Mode Pupitre Studio** : L'écran du PC affiche `/grid` (sélection & régie au touchpad/clavier/tactile), l'écran HDMI externe (TV/Vidéoprojecteur) diffuse `/cinema` sans boutons.
  - **Mode Headless** : Le laptop fonctionne capot fermé (*Clamshell mode*) comme un mini-PC headless. Si le capot reste ouvert, l'écran du laptop affiche l'administration complète (`/`), tandis que la sortie HDMI diffuse le flux configuré (`/kiosk` ou `/cinema`).
- **Sur Tablette Android** :
  - **Mode Pupitre Studio** : L'écran de la tablette affiche `/grid` en plein écran.
  - **Mode Headless** : L'application Bobine sur la tablette n'affiche pas `/grid` mais une page d'accueil sobre avec le logo Bobine, l'état de la diffusion HDMI en cours, un gros bouton bien visible **« Activer le mode Pupitre »**, et un lien discret vers l'Administration. La tablette reste allumée (compromis assumé sans extinction complète de l'écran afin de préserver l'alimentation du port HDMI sous Android).

---

## 2. Emplacement & Interface dans les Réglages (`/settings`)

Conformément à la directive d'architecture, la nouvelle section est positionnée dans `frontend/src/app/settings/page.tsx` :
- **Au-dessous** de la section **Palette Apparence** (thèmes clair/sombre, langue).
- **Au-dessus** de la section **Image de marque** (logo, branding).

### Maquette visuelle dans les Paramètres :

```
┌────────────────────────────────────────────────────────────────────────┐
│ [tv] Configuration d'affichage & Écrans                                │
│                                                                        │
│ Mode d'affichage de la sortie câblée (HDMI)                            │
│                                                                        │
│ ┌───────────────────────────────────┐ ┌──────────────────────────────┐ │
│ │ [view_quilt] Mode Pupitre Studio  │ │ [desktop_windows] Headless   │ │
│ │ (Double écran)                    │ │ (Écran unique)               │ │
│ │                                   │ │                              │ │
│ │ • Écran intégré : Grille /grid    │ │ • Écran intégré : Libre /    │ │
│ │ • Sortie HDMI : Cinéma épuré      │ │   Page d'accueil sobre       │ │
│ │ • Idéal pour piloter en direct    │ │ • Sortie HDMI : Kiosk/Cinéma │ │
│ │   au pupitre ou sur la tablette   │ │ • Idéal capot fermé ou Wyse  │ │
│ └───────────────────────────────────┘ └──────────────────────────────┘ │
│                                                                        │
│ 💡 En mode Pupitre, l'écran de votre tablette ou laptop sert de        │
│ régie tactile. En mode Headless, la sortie HDMI fonctionne de façon    │
│ autonome (compatible fermeture du capot sur PC portable).              │
└────────────────────────────────────────────────────────────────────────┘
```

> **Évolutivité Réseau** : Cette modélisation en base de données et dans l'interface prépare l'extension future au canal réseau (`network`), permettant de désigner ultérieurement n'importe quel écran déporté du LAN comme pupitre ou afficheur.

---

## 3. Comportement Validé par Plateforme

### 3.1 Sur Tablette Android

#### En Mode Pupitre Studio (`dual_screen`) :
- `MainActivity.kt` charge `http://127.0.0.1:8000/grid/`.
- `BobinePresentation.kt` charge `http://127.0.0.1:8000/cinema/`.
- L'écran HDMI n'affiche aucune commande tactile superposée (`cinema-controls`).

#### En Mode Headless (`headless`) :
- `MainActivity.kt` charge une page d'accueil sobre (`/grid-idle` ou état dédié de `/grid`) :
  - Logo Bobine centré.
  - Statut de diffusion HDMI en temps réel (cours en cours ou attente).
  - Bouton principal proéminent : **« Activer le mode Pupitre (/grid) »** qui bascule le réglage en direct.
  - Bouton secondaire : **« Administration »**.
- **La tablette reste allumée** : l'écran n'est pas éteint par le bouton Power pour éviter la coupure matérielle du contrôleur USB-C/HDMI imposée par le système Android.
- La sortie HDMI respecte scrupuleusement le choix du tableau de bord (`/kiosk` ou `/cinema`).

---

### 3.2 Sur Ordinateur Portable (Windows, macOS, Linux)

#### En Mode Pupitre Studio (`dual_screen`) :
- **Écran Laptop (Moniteur 1)** : Affiche `/grid`. L'utilisateur sélectionne ses cours à la souris, au touchpad ou au tactile et dispose du widget *Now Playing*.
- **Sortie HDMI (Moniteur 2)** : Affiche `/cinema` en mode passif épuré (aucune commande superposée sur la projection en salle).
- **Lancement par le Tray (`tray.py`)** : Ouvre les fenêtres correspondantes sur chaque moniteur.

#### En Mode Headless (`headless`) :
- **Sortie HDMI** : Affiche le flux configuré dans l'admin (`/kiosk` ou `/cinema` avec commandes tactiles/souris).
- **Gestion du capot fermé (Clamshell)** :
  - Avec l'option standard de l'OS *« Ne rien faire à la fermeture du capot »*, refermer le laptop éteint son écran tout en maintenant la sortie HDMI et le serveur actifs.
- **Écran Laptop (si capot ouvert)** :
  - `BobineTray` ouvre automatiquement le tableau de bord d'administration (`http://localhost:8000/`).

---

### 3.3 Sur Mini-PC Dédié (Dell Wyse 5070 / Appliance Headless)
- Par défaut en mode **Headless** (aucun écran intégré, sortie HDMI directe).
- Reste compatible avec le mode Pupitre si un écran tactile secondaire est raccordé sur le deuxième port DisplayPort.

---

## 4. Architecture Technique & Modifications de Code

### 4.1 Base de Données & Backend FastAPI
- **Table `settings`** :
  - Nouveau champ persistant : `wired_display_mode` : `"dual_screen" | "headless"`.
  - Valeur par défaut : `"headless"` sur desktop/linux-headless, `"dual_screen"` sur android.
- **Endpoints REST (`backend/app/routers/settings.py`)** :
  - Prise en charge dans `GET /api/settings` et `PUT /api/settings`.
- **Diffusion Temps Réel (`backend/app/routers/playback.py`)** :
  - Diffusion WebSocket d'un événement `display_mode_change` sur le canal `cable` pour que tous les écrans connectés réagissent instantanément sans nécessiter de rafraîchissement manuel.

### 4.2 Frontend Next.js
- **Page Réglages (`frontend/src/app/settings/page.tsx`)** :
  - Insertion du bloc visuel sous "Apparence" et au-dessus de "Image de marque".
  - Sélecteur de cartes élégantes avec icônes Material Symbols (`view_quilt` et `desktop_windows`).
- **Composant `/cinema` (`frontend/src/app/cinema/page.tsx`)** :
  - Conditionnement de l'affichage des contrôles HDMI :
    `const hideControls = wiredDisplayMode === "dual_screen";`
- **Route `/grid` ou écran de transition** :
  - En mode `headless`, rendu de l'interface sobre d'accueil avec statut HDMI et bouton de bascule vers le mode Pupitre.

### 4.3 Desktop Tray (`backend/app/desktop/tray.py`)
- Détection du mode actif au démarrage :
  - Si `wired_display_mode === "dual_screen"` : ouvre `/grid` sur l'écran principal et `/cinema` sur l'écran HDMI.
  - Si `wired_display_mode === "headless"` : ouvre `/cinema` ou `/kiosk` sur l'écran HDMI et l'administration sur l'écran du laptop.

### 4.4 Règles de Design d'Élite & Thèmes Dynamiques
- **Valeurs par défaut rigoureuses** :
  - Sur Desktop (Windows, macOS, Linux bureau) et Mini-PC (Wyse) : `"headless"` par défaut (affichage classique historique, aucune surprise au premier lancement).
  - Sur Tablette Android : `"dual_screen"` par défaut (exploite immédiatement le tactile et le dock HDMI).
- **Zéro couleur codée en dur** :
  - Toutes les surfaces utilisent exclusivement les design tokens CSS (`var(--bg-main)`, `var(--bg-surface-elevated)`, `var(--border-color)`, `var(--text-main)`, `var(--text-dim)`, `var(--accent-primary)`, `var(--accent-primary-fg)`).
  - Prise en charge immédiate et dynamique de la palette complète de thèmes (Clair, Sombre, Charbon Sombre, etc.) sans aucun clignotant ni incohérence.
- **Finitions d'Élite** :
  - Verre dépoli (`backdrop-filter: blur(24px)`), coins adoucis (`border-radius: var(--radius-lg)`), ombres portées douces.
  - États `:active` soignés avec réduction d'échelle fluide (`transform: scale(0.98)`).
  - Rigueur d'accessibilité : contrastes WCAG AA / AAA respectés sur tous les thèmes.

---

## 5. Découpage en Lots d'Implémentation

1. **Lot 1 — Persistance Backend & API** :
   - Ajout de `wired_display_mode` dans les modèles et le routeur de réglages.
   - Diffusion de l'événement WebSocket lors du changement.
2. **Lot 2 — Interface Utilisateur dans Réglages** :
   - Ajout de la section dans `settings/page.tsx` (sous Apparence, au-dessus de Branding).
   - Intégration i18n (FR / EN).
3. **Lot 3 — Adaptation de `/grid` & Page de Switch Tablette** :
   - Affichage de la vue sobre avec bouton de switch quand `wired_display_mode === "headless"`.
   - Réactivité instantanée lors du changement depuis l'admin ou depuis le bouton de la tablette.
4. **Lot 4 — Adaptation de `/cinema` & Desktop Tray** :
   - Masquage des contrôles HDMI en mode double-écran.
   - Mise à jour de `tray.py` pour orchestrer les fenêtres selon le mode choisi.
