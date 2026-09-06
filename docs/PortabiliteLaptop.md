# Cahier des charges & Faisabilité — Portabilité Laptop & Mode Pupitre Studio

> Document prospectif détaillant l'exploitation de Bobine sur un ordinateur portable (Windows, macOS, Linux) en configuration multi-écrans (écran intégré + sortie HDMI/vidéoprojecteur).

---

## 1. Vision & Cas d'Usage (Le PC Portable "Pupitre Studio")

Dans de nombreuses structures (salles de sport indépendantes, studios de yoga, hôtels, associations, entreprises), l'acquisition d'un mini PC dédié et de câblages muraux complexes peut représenter un frein. Un simple **PC portable** (déjà possédé ou d'occasion) branché en HDMI à un vidéoprojecteur ou téléviseur constitue une solution tout-en-un ultra-accessible.

### 1.1 Le piège de la duplication d'écran ("Miroir")
Dupliquer l'écran du laptop sur le vidéoprojecteur est inadapté à un usage en salle :
- **Pollution visuelle** : Le déplacement du curseur de la souris, les fenêtres système, les notifications d'OS et les clics sont projetés en grand format devant les adhérents.
- **Dilemme ergonomique & sécurité** :
  - Si le laptop affiche l'écran de diffusion (`/kiosk` ou `/cinema`), l'écran du laptop est "bloqué" et ne sert à rien.
  - Si le laptop affiche l'administration complète (`/`), les adhérents ont accès aux paramètres sensibles (suppression de vidéos, arrêt des services, réinitialisation de base de données).

### 1.2 La solution : Le Bureau Étendu & l'interface "Pupitre Studio" (`/desk`)
L'ordinateur portable est configuré en mode **Bureau Étendu** :
1. **Écran externe (HDMI / Vidéoprojecteur - Face à la salle)** :
   - Affiche le flux immersif plein écran sans aucune pollution (`/cinema` en diffusion de cours, `/kiosk` en attente avec logo, horloge et décompte).
2. **Écran intégré du Laptop (Face au coach ou à l'accueil du studio)** :
   - Affiche une nouvelle interface **"Pupitre Studio" (`/desk`)**, conçue pour être manipulée au clavier, au touchpad ou à l'écran tactile par les coachs et les adhérents.

```
┌────────────────────────────────────────┐          HDMI          ┌────────────────────────────────────────┐
│         Écran du PC Portable           │───────────────────────▶│     Vidéoprojecteur / TV du Studio     │
│       (Pupitre Studio / Accueil)       │                        │            (Face à la salle)           │
│                                        │                        │                                        │
│  ┌──────────────────────────────────┐  │                        │                                        │
│  │   Interface Pupitre (/desk)      │  │                        │          Diffusion Plein Écran         │
│  │                                  │  │                        │                                        │
│  │ • Catalogue de cours On-Demand   │  │                        │    • Cours vidéo 4K/1080p (/cinema)    │
│  │ • Planning interactif du jour    │  │                        │    • Écran d'attente animé (/kiosk)    │
│  │ • Console Régie / Coach          │  │                        │    • Zéro curseur, zéro menu visible   │
│  │ • Verrouillage Admin par PIN     │  │                        │                                        │
│  └──────────────────────────────────┘  │                        │                                        │
└────────────────────────────────────────┘                        └────────────────────────────────────────┘
```

---

## 2. Spécifications de l'Interface "Pupitre Studio" (`/desk`)

L'interface `/desk` est une route Next.js dédiée, stylisée avec les design tokens de Bobine (`frontend/src/app/globals.css`), optimisée pour le format laptop (1366×768 à 1920×1080) et le tactile :

### 2.1 Mode "Borne Adhérent" (Hors cours)
Lorsque la salle est disponible, l'écran propose un parcours en libre-service sécurisé :
- **Catalogue interactif "À la demande"** :
  - Grandes tuiles visuelles avec titre, vignette, discipline (Cycling, HIIT, Yoga, Pump, etc.), niveau et durée.
  - Filtres rapides : durée (`< 30 min`, `45 min`, `60 min`), matériel nécessaire.
  - Fiche détaillée du cours avec bouton d'action : **« Lancer ce cours dans le studio »**.
  - Possibilité d'activer une temporisation de confort (ex: "Le cours débutera dans 2 minutes, préparez votre matériel").
- **Planning interactif** :
  - Consultation de la grille horaire de la journée ou de la semaine.
  - Indicateur visuel du prochain cours programmé automatiquement.

### 2.2 Mode "Régie Coach" (Pendant un cours)
Dès qu'un cours est en cours de lecture sur la sortie HDMI, l'interface du laptop bascule en régie simplifiée :
- **Retour vidéo discret** : Petite vignette montrant ce qui défile sur le grand écran.
- **Chronomètre géant** : Temps écoulé / temps restant à la seconde près.
- **Contrôles de diffusion essentiels** :
  - Bouton **Pause / Reprendre** immédiat.
  - Bouton **Arrêter le cours** (avec confirmation simple pour éviter les clics accidentels).
  - Réglage rapide du **Volume sonore**.
- **Gestion des enchaînements** : Affichage du cours ou de la musique suivante.

### 2.3 Sécurité & Protection de l'Administration
Pour préserver l'intégrité du système lorsque le laptop est accessible aux adhérents :
- **Code PIN d'administration** :
  - Un bouton discret « Accès Administration » est logé en haut à droite.
  - Un pavé numérique virtuel demande un code PIN (configurable dans `/settings`, ex: 4 chiffres par défaut).
  - Une fois déverrouillé, l'utilisateur accède au studio complet (`/`, gestion des vidéos, plannings, playlists, réglages).
  - Verrouillage automatique après 5 minutes d'inactivité sur l'administration.
- **Interdictions strictes sur `/desk`** :
  - Impossible d'importer ou supprimer des fichiers multimédias.
  - Impossible de modifier les plannings système.
  - Impossible de réinitialiser la base de données ou de couper les services.

---

## 3. Architecture Technique & Intégration

### 3.1 Backend & Base de données
- **Nouveau réglage SQLite (`settings`)** :
  - `desk_pin_code` : Hash du code PIN pour le déverrouillage de l'admin depuis le pupitre (défaut : `"1234"` ou désactivé).
  - `desk_default_mode` : `"on_demand"` (catalogue libre-service) ou `"schedule_only"` (consultation uniquement).
- **Communication temps réel** :
  - `/desk` se connecte au WebSocket `/ws/playback` existant pour recevoir en direct les changements d'état du canal câblé (`cable`).

### 3.2 Gestion multi-écrans sur Desktop (`BobineTray`)
Dans `backend/app/desktop/tray.py`, enrichir l'application de barre des tâches :
- Détection des moniteurs connectés via les APIs système :
  - Windows : `EnumDisplayMonitors` (Win32 API).
  - Linux : `xrandr` / Wayland outputs.
  - macOS : `NSScreen.screens`.
- Option de menu dans le Tray :
  - **« Démarrer le mode Studio (Laptop + Vidéoprojecteur) »** :
    - Lance le navigateur en mode kiosque borderless sur l'écran secondaire (HDMI) avec `http://localhost:8000/cinema`.
    - Lance le navigateur sur l'écran principal (Laptop) avec `http://localhost:8000/desk`.

---

## 4. Feuille de route estimative

1. **Jalon 1 : Route Frontend `/desk`** (2 jours)
   - Création de la page `frontend/src/app/desk/page.tsx` avec les modes *Catalogue* et *Régie Coach*.
   - Intégration de la modale de déverrouillage par code PIN.
2. **Jalon 2 : Configuration Backend & Sécurité PIN** (1 jour)
   - Ajout de `desk_pin_code` dans `backend/app/routers/settings.py`.
   - Endpoint de vérification `/api/settings/verify-pin`.
3. **Jalon 3 : Détection multi-moniteurs dans BobineTray** (1 jour)
   - Prise en charge de la disposition double-écran automatique dans `tray.py`.
