# Cahier des Charges — Bobine V3.0.5 Bêta
# Métriques d'Assiduité, Notation 5 Étoiles & Moteur Vidéo Gapless A/B

---

## 1. Vision & Objectifs de la Version 3.0.5

La version **3.0.5** fait franchir à Bobine une étape stratégique en combinant excellence de diffusion vidéo et intelligence d'exploitation sportive locale :
1. **Module Métriques & Insights Club (100% Local & RGPD)** :
   - Tableau de bord dédié **« Métriques »** dans la barre latérale d'administration (sous **Planning**).
   - Notation par **5 étoiles** à la fin de chaque séance sur le grand écran (`/cinema`) et sur le pupitre coach (`/grid`).
   - Fermeture automatique du widget de notation après **5 minutes** si aucune interaction.
   - Suivi exhaustif des taux de complétion, des cours plébiscités, du volume horaire et des heures de pointe.
2. **Moteur Vidéo Double Décodeur A/B Deck (Gapless)** :
   - Élimination absolue des écrans noirs entre l'écran d'attente et le cours, ainsi qu'entre les cours d'une playlist, grâce à deux instances de lecture vidéo montées en continu avec transition douce en fondu enchaîné.

---

## 2. Spécifications du Module Métriques & Notation

### 2.1 Navigation & Placement
- **Barre latérale gauche** : Entrée insérée immédiatement en dessous de **Planning** (`/schedule`).
- **Route Next.js** : `/metrics`.
- **Icône** : Google Material Icon `analytics` (règle absolue : aucun emoji dans toute l'interface).
- **Intégration i18n** :
  - Clé `nav.metrics` : `"Métriques"` (FR) / `"Metrics"` (EN).

### 2.2 Système de Notation 5 Étoiles
- **Déclenchement** : À la fin naturelle d'un cours vidéo (`video_ended`) ou lorsque la progression dépasse 95% du temps total.
- **Affichage sur le Pupitre Coach (`/grid`)** :
  - Le widget flottant supérieur droit (`.grid-now-playing`) se métamorphose en carte d'évaluation tactile.
  - 5 étoiles cliquables (Google Icons `star` / `star_outline`) avec coloration dynamique selon la variable `--accent-primary` du thème actif.
  - Indicateur temporel discret : barre de progression fine ou décompte de **5 minutes** (300 secondes) avant auto-fermeture.
  - Bouton de fermeture manuelle immédiate (Google Icon `close`).
- **Affichage sur le Grand Écran (`/cinema`)** :
  - Intégration sur l'écran cinématique de fin de cours (« À suivre »).
  - Contrôle 100% physique : sélectionnable directement à la **télécommande** (flèches + OK), à la **manette de jeu** (stick / D-Pad + bouton A), à la **souris** ou au **tactile** (aucun QR code requis).
  - Disparition automatique au bout de 5 minutes avec retour vers l'écran d'attente sobre du studio.
- **Modèle de données SQLite (`course_ratings`)** :
  ```python
  class CourseRating(Base):
      __tablename__ = "course_ratings"
      id: Mapped[int] = mapped_column(primary_key=True)
      video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
      rating: Mapped[int] = mapped_column()  # 1 à 5
      channel: Mapped[str] = mapped_column()  # 'cable' ou 'network'
      source: Mapped[str] = mapped_column()   # 'grid' ou 'cinema'
      created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
  ```

### 2.3 Sessions de Lecture & Assiduité
- **Modèle de données SQLite (`playback_sessions`)** :
  ```python
  class PlaybackSession(Base):
      __tablename__ = "playback_sessions"
      id: Mapped[int] = mapped_column(primary_key=True)
      video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
      channel: Mapped[str] = mapped_column()  # 'cable' ou 'network'
      started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
      ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
      duration_played_seconds: Mapped[float] = mapped_column(default=0.0)
      total_duration_seconds: Mapped[float] = mapped_column(default=0.0)
      completed: Mapped[bool] = mapped_column(default=False)
      launch_type: Mapped[str] = mapped_column()  # 'grid', 'cinema', 'schedule', 'kiosk'
  ```
- **Gestionnaire côté serveur (`playback_manager.py`)** :
  - Création de la session au démarrage (`launch` / `play`).
  - Clôture de la session lors de l'arrêt, du changement de vidéo ou de la fin naturelle.
  - Calcul automatique du statut `completed` (vrai si `duration_played_seconds / total_duration_seconds >= 0.90`).

### 2.4 Tableau de Bord Administrateur (`/metrics`)
Le tableau de bord synthétise les performances du club en 4 zones claires et aérées :
1. **Bandeau de Cartes KPI Supérieur** :
   - **Satisfaction Globale** : Moyenne générale sur 5 étoiles (Google Icon `star`), nombre d'avis exprimés et distribution visuelle (pourcentage de 5★, 4★, 3★, 2★, 1★).
   - **Taux de Complétion Moyen** : Pourcentage moyen de séances terminées jusqu'au bout (Google Icon `task_alt`).
   - **Volume de Diffusion** : Heures totales de cours diffusés sur la période (Google Icon `schedule`).
   - **Séances Lancées** : Nombre total de séances démarrées (Google Icon `play_circle`).
2. **Classement des Cours & Programmes Plébiscités** :
   - Tableau interactif avec miniatures 16:9, titre du cours, programme, note moyenne (étoiles), taux d'achèvement moyen et nombre total de séances.
   - Tri par popularité ou par note de satisfaction.
3. **Histogramme d'Affluence & Fréquentation Horaire** :
   - Graphique épuré en bâtons CSS (sans dépendance lourde externe) illustrant les heures de la journée les plus actives (créneaux du matin, midi, fin d'après-midi/soirée).
4. **Filtres de Période & de Canal** :
   - Sélecteur temporel : *7 derniers jours*, *30 derniers jours*, *Ce mois-ci*, *Tout l'historique*.
   - Sélecteur de canal : *Tous*, *Sortie Câblée (HDMI)*, *Sortie Réseau*.

---

## 3. Spécifications du Moteur Vidéo Gapless A/B Deck

### 3.1 Problématique Technique
Sur les navigateurs basés sur Chromium (mode Kiosque X11 sur Wyse, WebView Android, fenêtres de bureau Tauri/Electron), l'affectation d'un nouveau `video.src` entraîne la destruction du pipeline de décodage matériel existant et un temps de reconfiguration de la mémoire tampon vidéo. Cela génère inévitablement un écran noir visible (200 à 600 ms) entre l'écran d'attente et le début du cours, ou entre deux cours consécutifs d'une playlist.

### 3.2 Architecture de Double Décodeur Vidéo
- **Deux éléments vidéo persistants dans le DOM** :
  ```html
  <div className="cinema-deck-container">
    <video ref={deckARef} className="cinema-deck cinema-deck-a" />
    <video ref={deckBRef} className="cinema-deck cinema-deck-b" />
  </div>
  ```
- **Cycle de transition matérielle** :
  1. Le **Deck Actif** joue la vidéo en cours (`opacity: 1`, `zIndex: 2`, `muted: false`).
  2. Le **Deck en Attente** est préchargé en coulisses avec la vidéo suivante ou le fond de veille (`opacity: 0`, `zIndex: 1`, `muted: true`, `currentTime: 0`, `preload="auto"`).
  3. Dès confirmation de la disponibilité de la première trame (`canplay` / `seeked`), la transition est déclenchée :
     - Fondu enchaîné CSS matériel (`transition: opacity 0.4s ease`).
     - Bascule progressive du volume sonore pour éviter tout claquement audio (pop/click).
     - Le Deck B devient Actif, le Deck A devient Deck en Attente.
- **Résultat** : Zéro coupure, zéro flash noir, transitions d'une fluidité exemplaire.

---

## 4. Règles de Développement, Thèmes & Directives

- **Zéro Emoji** : Tous les indicateurs, étoiles de notation et boutons doivent employer exclusivement les icônes Google Icons vectorielles (`Icon name="..."`).
- **Conformité aux 16 Thèmes Bobine** : Adaptation stricte aux palettes (Nuance Nuit, Charbon Sombre, Glacier Clair, etc.) avec variables CSS sémantiques.
- **100% Hors-Ligne & Indépendant** : Aucune dépendance externe (pas de bibliothèque de graphiques tierce lourde), calculs SQL exécutés sur l'instance SQLite locale via SQLAlchemy.
- **Multi-Plateforme Intégral** : Fonctionne identiquement sur Appliance Dédiée Headless (Wyse 5070), Postes Linux de Bureau, Windows 11, macOS Apple Silicon et Tablette Android tactile (Xiaomi Pad 8).
