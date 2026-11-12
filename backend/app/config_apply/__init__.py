"""Application des fichiers de configuration (`app/config_files.py`) : tout ou rien.

Chaque fichier décrit l'état voulu de son type de réglage. Toutes les références (vidéos, pistes, morceaux, fonds,
playlists) sont d'abord résolues et toutes les valeurs validées, avec les mêmes règles que l'interface ; la moindre
erreur refuse l'ensemble et les liste toutes. Sinon tout est écrit dans une seule transaction, puis les effets à chaud
(diffusion aux écrans, planificateur, moteurs radio) suivent. L'essai à blanc renvoie l'écart sans rien écrire.

Reconnaissance des objets : par `uid` (identifiant stable) quand il est présent et connu ; sinon par le nom ou les
métadonnées, comme dans les fichiers de la version 5.1. Un `uid` inconnu ici crée l'objet avec ce `uid` (restauration
sur une autre installation) ; un objet reconnu par son `uid` dont le nom a changé est renommé.

Sémantique par fichier : réglages et sorties = valeurs fournies ; playlists et étiquettes = créées, renommées ou
remplacées, les autres restent sauf `"prune": true` (elles sont alors supprimées) ; `library/` = métadonnées des médias
existants (jamais de création ni de suppression de média) ; annonces = description et activation des annonces existantes ;
règles d'annonce et planning d'un canal = liste complète (ce qui n'y figure plus est supprimé, les `id` des programmations
reconnues sont conservés).
"""
