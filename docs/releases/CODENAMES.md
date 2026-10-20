# Noms de code des versions Stable

Chaque version **Stable** majeure ou marquante reçoit, en plus de son numéro `Vx.y.z`, un nom de code — un mot, choisi librement, sans thème imposé à l'avance. Objectif : donner un repère mémorable à une version marquante (« la version Orchidée »), pas remplacer le numéro de version, qui reste la seule source de vérité pour l'ordre et la comparaison (`_parse_version()`, `app.utils.version`).

## Où il apparaît

- **Titre de `docs/releases/Vx.y.z.md`** : `# Bobine Vx.y.z « Nom » — <sous-titre>` (voir `V5.0.0.md` pour l'exemple).
- Nulle part ailleurs pour l'instant : ni dans `VERSION`, ni dans l'API, ni dans l'interface. Le nom de code est un repère éditorial pour les notes de version et la communication, pas une donnée fonctionnelle — pas de dérive à craindre sur `_parse_version()`/`_rolling_build_info()` si ce fichier n'est jamais lu par du code.

## Convention

- Un nom par version **Stable** seulement (jamais pour Bêta/Canary, qui n'ont pas de notes dédiées : leurs notes sont générées automatiquement par la CI).
- Un seul mot, en français, capitalisé, jamais réutilisé (vérifier ce tableau avant d'en choisir un nouveau).
- Choisi au moment de rédiger les notes de version, pas avant — pas de nom réservé à l'avance pour une version pas encore sortie.

## Registre

| Version | Nom de code | Date |
| :--- | :--- | :--- |
| V5.0.0 | Orchidée | 2026-10-17 |
| V5.0.2 | Constellation | 2026-10-20 |
