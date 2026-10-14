#!/usr/bin/env python3
"""Lance un backend Bobine de TEST isolé, sans publication mDNS.

À démarrer avec des dossiers de données jetables, par exemple :
    BOBINE_USE_XDG=1 XDG_DATA_HOME=/tmp/bobine-bench/data XDG_CONFIG_HOME=/tmp/bobine-bench/cfg \
        backend/.venv/bin/python scripts/browser-bench/run_test_backend.py [port]
Ne touche jamais aux données de l'installation réelle ni ne s'annonce sur le
réseau local (`bobine.local`)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import app.utils.mdns as mdns  # noqa: E402

mdns.start_mdns_responder = lambda port: None  # rien sur le LAN pendant les tests

import uvicorn  # noqa: E402

uvicorn.run("app.main:app", host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8078, log_level="warning")
