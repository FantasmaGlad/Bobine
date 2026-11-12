"""Point d'entrée figé par PyInstaller en `BobineBackend.exe` (cf."""

import logging
import multiprocessing
import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r", encoding="utf-8")

import uvicorn

from app.config import settings
from app.main import app
from app.utils.port import PortUnavailableError, acquire_listen_port, release_port

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        listen_port = acquire_listen_port()
    except PortUnavailableError as exc:
        logging.getLogger("app.run_backend").error("%s", exc)
        print(f"Bobine : démarrage impossible. {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        uvicorn.run(app, host=settings.host, port=listen_port, workers=1, proxy_headers=False)
    finally:
        release_port()
