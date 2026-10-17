"""Détection d'Android indépendante de la version de CPython.

Chaquopy 3.12+ (arm64-v8a, x86_64) expose `sys.getandroidapilevel()` et
`platform.system() == "Android"`. Le runtime 3.11, seul à fournir
armeabi-v7a (boîtiers Android TV dont le système est 32 bits), n'en expose
aucun : `platform.system()` y vaut "Linux". Tout test de plateforme doit donc
passer par `is_android()` plutôt que par l'un de ces signaux isolés, sans quoi
le backend embarqué se prend pour un Linux de bureau (mauvais dossiers de
données, aucune accélération MediaCodec, mises à jour qui cherchent un `.deb`).

Module feuille : aucun import de `app.*`, utilisable dès `config.py`.
"""

import os
import platform
import sys


def is_android() -> bool:
    # Posée par `bobine_bootstrap.py` avant tout import de `app`, ce qui
    # couvre n'importe quelle version de CPython.
    if os.environ.get("BOBINE_PLATFORM") == "android":
        return True
    if hasattr(sys, "getandroidapilevel") or platform.system() == "Android":
        return True
    # Variables que le zygote pose dans tout processus d'application.
    return bool(os.environ.get("ANDROID_ROOT") and os.environ.get("ANDROID_DATA"))
