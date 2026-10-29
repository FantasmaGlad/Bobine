"""Point d'entrée figé par PyInstaller en `BobineBackend.exe` (cf.
`packaging/windows/bobine.spec`). Équivalent de
`uvicorn app.main:app --host 0.0.0.0 --port <port> --workers 1` en
développement, mais invoqué programmatiquement : `python -m uvicorn`
dépend d'un point d'entrée console-script qui n'existe plus une fois le
tout figé dans un seul exécutable.

Import direct de `app.main:app` (plutôt que la chaîne `"app.main:app"`
qu'accepte aussi `uvicorn.run`) : PyInstaller analyse statiquement les
imports pour décider quoi embarquer — une chaîne de caractères passée à
`uvicorn.run` ne lui apprend rien, et le paquet `app` se retrouvait
absent du binaire figé (`ModuleNotFoundError: No module named 'app'`,
constaté à l'exécution réelle). Un objet d'app importé directement reste
valide avec `workers=1` (aucun rechargement à chaud ni sous-process
supplémentaire à réimporter — seul `workers > 1` exige une chaîne, pour
que chaque worker puisse réimporter l'app dans son propre process).

Le port d'écoute n'est plus figé : `acquire_listen_port()` (app/utils/port.py)
renvoie le port configuré (`settings.port`) s'il est libre, sinon un port de
repli, et le publie dans le fichier d'exécution lu par la barre d'état.
`BOBINE_PORT_STRICT=1` interdit le repli : le démarrage échoue avec un message
clair (appliance systemd).
"""

import logging
import multiprocessing
import os
import sys

# Sous Windows sans console (ou si les flux standards sont None), rediriger
# vers os.devnull pour éviter tout plantage d'uvicorn/logging sur AttributeError
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r", encoding="utf-8")

import uvicorn

from app.main import app
from app.utils.port import PortUnavailableError, acquire_listen_port, release_port

if __name__ == "__main__":
    # No-op sur Linux/hors gel (cf. doc Python) ; requis sur Windows/macOS
    # frozen si une dépendance venait à utiliser `multiprocessing` en interne
    # (aucun usage direct ici avec workers=1, mais un import manquant de ce
    # garde-fou provoquerait un boot loop silencieux si jamais le cas se
    # présentait — coût nul de le poser dès maintenant).
    multiprocessing.freeze_support()
    try:
        listen_port = acquire_listen_port()
    except PortUnavailableError as exc:
        # Journal technique (déjà configuré par app.main) ET flux d'erreur :
        # le superviseur (systemd, barre d'état) lit l'un ou l'autre.
        logging.getLogger("app.run_backend").error("%s", exc)
        print(f"Bobine : démarrage impossible. {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        uvicorn.run(app, host="0.0.0.0", port=listen_port, workers=1)
    finally:
        release_port()
