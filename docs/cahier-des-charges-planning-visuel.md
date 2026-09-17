# Cahier des charges — Planning Visuel (Timeline proportionnelle)

> Spécification fonctionnelle et technique pour la refonte de la vue Calendrier de `/schedule` : miniatures par type de média, blocs proportionnels à la durée réelle, granularités Jour/Semaine à la Google Calendar, et coupure propre entre programmations qui se chevauchent sur les 3 canaux (Câblé, Réseau, Radio).

---

## 1. Contexte & Objectifs

### 1.1 Constat sur l'existant

`frontend/src/app/schedule/page.tsx` propose aujourd'hui deux vues (`viewMode: "calendar" | "list"`) :
- **Vue Calendrier** : une grille de 7 colonnes (une par jour), chaque programmation étant une **chip** de taille uniforme empilée verticalement dans sa journée — aucune proportionnalité à l'heure ni à la durée, pas de miniature. Desktop uniquement (le mobile retombe toujours sur la vue Liste, `if (isMobile) setViewMode("list")`).
- **Vue Liste** : mêmes chips, regroupées par jour, format compact.

Ni l'une ni l'autre ne permet de voir en un coup d'œil : ce qui va être diffusé (miniature), combien de temps ça va occuper l'écran (durée visuelle), ni si deux programmations se chevauchent dans le temps.

Côté moteur de diffusion (`backend/app/scheduler_manager.py::_launch_target`), le comportement de coupure existe déjà **partiellement** :
- **Câblé** : une programmation qui se déclenche coupe toujours ce qui est en cours (manuel ou programmé) et mémorise une position de reprise (`PlaybackState`, cause `"schedule"`).
- **Réseau** : règle inversée — une lecture manuelle en cours gagne toujours, une programmation qui arrive en même temps est annulée silencieusement.
- **Radio** : sous-système indépendant (D8) — une fenêtre programmée charge une playlist en boucle, revient à l'ambiance par défaut (`_revert_radio_to_default`) à la fin de sa fenêtre (`end_time`) ou reste permanente en mode `24_7`.

Aucune des trois branches ne distingue aujourd'hui *"ce qui joue est un reliquat d'une programmation précédente encore active"* d'un *"vrai lancement manuel"* — cette distinction n'existe nulle part dans l'état de lecture en mémoire (`PlaybackManager.snapshot()`). C'est ce qui, sur le canal Réseau, ferait **annuler silencieusement** une deuxième programmation qui chevauche la première au lieu de couper proprement dessus.

### 1.2 Objectifs validés (décisions prises le 2026-09-17)

1. Vue Calendrier repensée façon **Google Calendar** : granularités **Jour** et **Semaine** (pas de vue Mois — peu lisible avec des blocs proportionnels à la minute).
2. Chaque programmation affiche sa **miniature** (vidéo, playlist vidéo, ou radio) et un bloc dont la **taille est proportionnelle à sa durée réelle**, avec un **contrôle de zoom** pour garder lisibles aussi bien un cours de 45 min qu'une playlist de 600 min sur le même écran.
3. Le chevauchement de deux programmations est **autorisé à la création**, sans blocage ni avertissement — seulement **signalé visuellement** sur le planning (le bloc qui commence après indique clairement qu'il coupera le précédent).
4. **"Le dernier qui se lance coupe proprement ce qui est en cours" s'applique aux 3 canaux** (Câblé, Réseau, Radio) entre deux programmations qui se chevauchent — ce qui suppose un correctif du moteur de diffusion sur le canal Réseau (cf. §5).
5. La vue **Liste** existante n'est pas concernée par cette refonte (elle garde son format actuel de chips compactes) — seule la vue **Calendrier** devient la timeline proportionnelle Jour/Semaine.
6. **Mobile** : Jour + Liste uniquement, pas de Semaine (compromis de lisibilité jugé non rentable sur écran de téléphone — cf. §7 pour le détail et la justification).

---

## 2. Représentation visuelle par type de média

### 2.1 Vidéo (`target_type: "video"`)

- **Miniature** : `Video.thumbnail_path` (déjà généré à l'import), identique à celle utilisée dans Bibliothèque.
- **Durée du bloc** : `Video.duration_seconds` — proportionnelle à l'échelle courante du calendrier (cf. §3).

### 2.2 Playlist vidéo (`target_type: "playlist"`)

- **Miniature** : `Playlist` n'a **aucun champ cover aujourd'hui** (`backend/app/models.py:149-158`). Convention retenue, identique à celle déjà en place pour `RadioPlaylist.cover_path` (dérivation si absent) : **miniature du premier élément de la playlist** (`playlist.items[0].video.thumbnail_path`, trié par `position`). Aucune migration de schéma nécessaire.
- **Durée du bloc** : somme des `duration_seconds` de tous les items (déjà exposée par l'API playlists existante, `total_duration_seconds`).

### 2.3 Radio — fenêtre programmée (`target_type: "radio_playlist"`, récurrente avec `end_time`)

- **Miniature** : `RadioPlaylist.cover_path` si renseigné, sinon pochette du premier morceau (`RadioPlaylistItem` trié par `position`) — même convention déjà utilisée par le module Radio lui-même.
- **Durée du bloc** : **PAS** la durée de la playlist (qui boucle indéfiniment). Le bloc dure de `time_of_day` à `end_time` (la fenêtre choisie par l'admin), exactement comme un événement de calendrier classique — décision validée en §1.2.4.

### 2.4 Radio — ambiance permanente (`mode: "24_7"`, ou aucune fenêtre programmée active)

- Représentée comme une **bande de fond discrète**, en arrière-plan sur toutes les plages horaires non couvertes par une autre programmation (vidéo/playlist/fenêtre radio explicite) — décision validée. Ne bloque ni ne masque les blocs normaux, qui restent dessinés par-dessus.
- S'applique aussi bien à une `RadioPlaylist.is_default` explicite qu'au repli "toute la bibliothèque en aléatoire" (`_launch_radio_shuffle_all`) quand aucune playlist par défaut n'existe — dans les deux cas, c'est la même bande "ambiance par défaut active".

---

## 3. Échelle temporelle & zoom

- **Proportionnalité stricte** : un bloc de 600 min est visuellement ~13× plus long qu'un bloc de 45 min à l'échelle courante (décision validée, §1.2.2).
- **Contrôle de zoom** : un curseur/bouton +/- ajuste le nombre de pixels par minute affiché, pour permettre de voir une journée entière avec un cours ponctuel ET une playlist de 10h sans scroll démesuré à l'échelle la plus dézoomée, tout en gardant une échelle plus lisible (proche de l'existant Google Calendar, ~1h = 60-80px) au zoom par défaut.
- Le zoom est un réglage de **vue** (état local UI, pas persisté en base) — cohérent avec le reste de `/schedule` qui ne persiste aucune préférence d'affichage aujourd'hui.

---

## 4. Vues Jour / Semaine

- **Vue Jour** : une seule colonne, règle horaire verticale 00:00–23:59, blocs proportionnels dans cette colonne.
- **Vue Semaine** : 7 colonnes (comme aujourd'hui), même règle horaire, chaque colonne devient une mini-timeline verticale au lieu d'un empilement de chips uniformes.
- Bascule Jour ⇄ Semaine : boutons dans la barre d'outils existante (`.schedule-toolbar`), à côté du sélecteur Calendrier/Liste actuel.
- Navigation (jour précédent/suivant, semaine précédente/suivante, "Aujourd'hui") : reprend le principe déjà présent pour la navigation de semaine actuelle.

---

## 5. Chevauchement : affichage et comportement de diffusion

### 5.1 À la création (éditeur de programmation)

Aucun blocage ni avertissement (décision validée, §1.2.3). Le formulaire de création/édition (`openEditDrawer` / drawer existant) reste inchangé sur ce point.

### 5.2 Sur le planning (affichage)

Deux programmations qui se chevauchent dans le temps sont dessinées **toutes les deux**, positionnées côte à côte (ou superposées avec un léger décalage, comme les événements qui se chevauchent dans Google Calendar) plutôt que l'une masquant l'autre. Celle qui **commence en second** porte une indication visuelle explicite (ex. icône ciseaux / bordure distincte + info-bulle "coupera [Titre du premier bloc] à son démarrage").

### 5.3 Au moment de la diffusion (moteur, `scheduler_manager.py`)

**Règle unifiée validée sur les 3 canaux** : quand une programmation se déclenche alors qu'une AUTRE programmation (câblé/réseau) ou fenêtre radio est encore active pour le même canal, la nouvelle coupe systématiquement l'ancienne, sans jamais être annulée.

**Correctif nécessaire (canal Réseau)** : `_launch_target` calcule aujourd'hui `manual_video_active` uniquement à partir de l'état de lecture (`current["state"]`, `current["current_video"]`), sans savoir si ce qui joue a été lancé **manuellement** ou par une **programmation précédente encore en cours**. Sur le canal Réseau, la règle "le manuel gagne toujours" s'applique donc par erreur aussi à un chevauchement programmation-vs-programmation, entraînant une annulation silencieuse de la seconde au lieu de la coupure attendue.

Piste d'implémentation : exposer l'origine du lancement courant dans `PlaybackManager.snapshot()` (un champ dérivé du `launch_type` déjà utilisé pour les métriques — `"schedule"` vs `"grid"/"cinema"/"kiosk"` — mais jamais stocké sur l'état de lecture en mémoire aujourd'hui, seulement en base pour l'analytics `/metrics`). `manual_video_active` devient alors : *lecture en cours ET état actif ET origine ≠ "schedule"* — ce qui laisse la règle "manuel gagne" intacte pour un vrai conflit manuel-vs-programmation sur le Réseau, tout en laissant une programmation couper une AUTRE programmation encore active, sur les deux canaux.

**Radio** : `_launch_radio_target` remplace déjà intégralement la lecture en cours par un simple `load_playlist()`, sans notion de conflit manuel — une fenêtre radio qui démarre coupe donc déjà nativement la précédente (playlist ou fenêtre radio antérieure). Aucun correctif requis côté radio pour ce point ; seule la représentation visuelle (§2.3/§2.4) est nouvelle.

---

## 6. Impacts techniques (vue d'ensemble, à affiner en implémentation)

### Backend

- `scheduler_manager.py::resolve_target_title` (ou une fonction sœur) : étendre pour retourner aussi `duration_seconds` et une URL de miniature par type de cible (vidéo directe, 1er item pour une playlist, `cover_path`/1er morceau pour une radio playlist).
- `routers/schedule.py::_to_response` / `OccurrenceResponse` : ajouter les champs `duration_seconds`, `thumbnail_url`, et pour une fenêtre radio, `end_time` déjà disponible via `recurrence_rule` (à exposer aussi sur l'occurrence résolue, pas seulement sur la programmation parente).
- `playback_manager.py` : exposer l'origine du lancement (`launch_type` ou équivalent) dans `snapshot()`.
- `scheduler_manager.py::_launch_target` : corriger `manual_video_active` (cf. §5.3).

### Frontend

- `app/schedule/page.tsx` : nouvelle sous-vue "Calendrier proportionnel" avec règle horaire, positionnement des blocs par `top/height` (vue Jour) ou `top/height` par colonne (vue Semaine), calculés depuis `run_at` + `duration_seconds` + l'échelle de zoom courante.
- Nouveau composant de bloc réutilisable (miniature + titre + durée + indicateur de chevauchement), partagé entre vue Jour et vue Semaine.
- Bande de fond radio 24/7 : couche séparée sous les blocs normaux, calculée à partir de l'absence de programmation active sur chaque plage.

---

## 7. Adaptation mobile (décision validée le 2026-09-17)

Le calendrier proportionnel à 7 colonnes n'a pas sa place sur un écran de téléphone (~360-430px) : à cette largeur, chaque colonne de jour ferait ~50px, trop étroit pour un bloc lisible avec sa miniature — on retomberait sur de simples barres de couleur sans titre ni image, une version dégradée qui n'apporte rien de plus que la vue Liste existante (qui couvre déjà bien le besoin "vue d'ensemble de la semaine" sur mobile, raison pour laquelle le mobile y est aujourd'hui forcé).

Décision retenue, cohérente avec le seuil mobile déjà utilisé partout dans l'app (`useIsMobile`, ≤768px) :

- **Vue Jour** : accessible sur mobile — c'est la seule granularité "calendrier" qui a un sens en une seule colonne verticale (timeline proportionnelle, miniatures, zoom). Navigation jour précédent/suivant pour parcourir la semaine sans avoir besoin d'une vue d'ensemble compressée.
- **Vue Semaine** : **masquée sur mobile**, comme le calendrier grille actuel l'est déjà (`if (isMobile) setViewMode("list")`). Pas de version "adaptée" en colonnes étroites — le compromis de lisibilité ne vaut pas la complexité d'implémentation supplémentaire.
- **Vue Liste** : reste le repli existant, inchangée.
- **Zoom tactile** : boutons +/- plutôt qu'un curseur fin (peu maniable au doigt) ; le survol (indication de chevauchement, cf. §5.2) devient un **tap** qui déplie les informations du bloc, cohérent avec le reste de l'app sur tactile (pas de hover natif).

Le sélecteur de vue affiche donc, sur mobile : **Jour | Liste** (Semaine disparaît du sélecteur, comme Calendrier/Liste aujourd'hui) ; sur desktop/tablette (≥769px) : **Jour | Semaine | Liste**.

---

## 8. Points ouverts / hors périmètre

- **Vue Mois** : explicitement exclue (§1.2.2).
- **Windows/macOS et détection d'écran câblé** : sujet distinct, déjà tranché séparément (décision d'architecture du 2026-09-17) — statu quo volontaire, non lié à ce CDC.
- **Persistance du niveau de zoom** : non spécifiée — traitée comme un réglage de session (état local), à confirmer si un besoin de persistance par utilisateur émerge.
