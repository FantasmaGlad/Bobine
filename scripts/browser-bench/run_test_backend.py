#!/usr/bin/env python3
"""Lance un backend Bobine de TEST isolé, sans publication mDNS."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import app.utils.mdns as mdns  # noqa: E402

mdns.start_mdns_responder = lambda port: None

import uvicorn  # noqa: E402

uvicorn.run("app.main:app", host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8078, log_level="warning", proxy_headers=False)
