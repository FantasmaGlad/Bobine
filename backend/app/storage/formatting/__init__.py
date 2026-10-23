"""Assistant de formatage du stockage externe (action destructive, en deux phases et sous garde-fous en cascade).

* `model` / `disks` : support vu comme un DISQUE (table de partitions, partitions, montages) et son identité ;
* `rules` : cascade de vérifications PURES, appliquée au plan puis de nouveau juste avant d'écrire ;
* `options` : systèmes de fichiers proposés, étiquettes, paramètres de formatage adaptés à la capacité ;
* `tokens` : jeton court, à usage unique, lié à l'identité du support ;
* `content` : résumé borné du contenu (ce qui sera effacé) ;
* `manager` : plan, exécution, annulation avant le point de non-retour, vérification après coup.

Rien ici n'écrit sur un support avant que `manager` ait franchi toute la cascade.
"""
