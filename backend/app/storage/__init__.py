"""Stockage externe : détection à chaud, exploration, import, bibliothèque externe, longévité.

Organisation (aucune dépendance entre les modules purs et le reste de l'application) :

* `types`, `lsblk`, `fsadvisor`, `health`, `longevity`, `paths` : logique PURE, testée sans matériel ;
* `drivers/` : un pilote par plateforme (Linux livré ; Windows, macOS, Android : `NullStorageDriver`
  explicite), même patron que `app/devices/` ;
* `availability` : registre en mémoire des supports en ligne (aucune E/S par ligne de base de données) ;
* `library`, `transfer` : base de données, copie vérifiée, indexation ;
* `service` : surveillance, évènements WebSocket, remappage des chemins.
"""
