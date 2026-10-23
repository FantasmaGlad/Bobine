"""Configuration commune des tests.

Les dossiers temporaires de pytest sont fixés AVANT l'import de l'application : `app/main.py` redirige `tempfile.tempdir`
vers `data/tmp` (uploads sur le disque des médias), et des tests du stockage externe créent des liens symboliques
(vers `/etc`, vers leur propre dossier) pour vérifier qu'ils ne sont jamais suivis. Sous `backend/data/`, la collecte de
pytest les parcourrait à l'exécution suivante."""

import tempfile
from pathlib import Path


def pytest_configure(config):
    if getattr(config.option, "basetemp", None) is None:
        config.option.basetemp = Path(tempfile.gettempdir()) / "pytest-bobine"
