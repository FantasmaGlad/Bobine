"""Détection d'Android indépendante de la version de CPython."""

import os
import platform
import sys


def is_android() -> bool:
    if os.environ.get("BOBINE_PLATFORM") == "android":
        return True
    if hasattr(sys, "getandroidapilevel") or platform.system() == "Android":
        return True
    return bool(os.environ.get("ANDROID_ROOT") and os.environ.get("ANDROID_DATA"))
