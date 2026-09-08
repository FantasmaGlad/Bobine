"""Test minimal du Lot 0 (cf. docs/plan-implementation-android.md) :
importer un par un les paquets de backend/requirements.txt une fois
installes par Chaquopy, pour distinguer un paquet qui echoue a
l'INSTALLATION (visible des la synchronisation Gradle / le pip install,
avant meme d'arriver ici) d'un paquet installe mais qui echoue au
CHARGEMENT sur l'appareil (symbole natif manquant, etc. - visible
seulement ici, a l'execution reelle).

Ne remplace pas un import reel de `app.main` (le vrai backend) : ce
dernier est reporte au Lot 2, qui doit d'abord resoudre proprement
l'inclusion du dossier backend/app/ sans embarquer .venv/, data/,
tests/, alembic/ (cf. Decouvertes du Lot 0 dans le plan).
"""

# Nom du paquet pip -> module(s) Python a importer pour le verifier.
_PACKAGES = {
    "fastapi": ["fastapi"],
    "uvicorn": ["uvicorn"],
    "sqlalchemy": ["sqlalchemy"],
    "alembic": ["alembic"],
    "watchdog": ["watchdog.observers"],
    "python-multipart": ["multipart"],
    "apscheduler": ["apscheduler"],
    "tzlocal": ["tzlocal"],
    "aiofiles": ["aiofiles"],
    "pillow": ["PIL"],
    "psutil": ["psutil"],
    "pystray": ["pystray"],
    "zeroconf": ["zeroconf"],
    # Pydantic v1 (pas v2) sur ce profil - cf. Decouvertes du plan Lot 0 :
    # pydantic-core (extension Rust de Pydantic v2) n'a aucune distribution
    # Android reelle (pip installait silencieusement un placeholder vide de
    # 2022). Downgrade Pydantic v1 + fastapi==0.99.1, decision utilisateur.
    "pydantic (v1)": ["pydantic"],
}


def run():
    """Retourne (nb_ok, nb_total, details) - appele depuis Kotlin."""
    results = []
    ok_count = 0
    for label, modules in _PACKAGES.items():
        try:
            for m in modules:
                __import__(m)
            results.append(f"OK   {label}")
            ok_count += 1
        except Exception as exc:  # volontairement large : on veut TOUT capturer pour le rapport
            results.append(f"FAIL {label}: {type(exc).__name__}: {exc}")
    return ok_count, len(_PACKAGES), "\n".join(results)
