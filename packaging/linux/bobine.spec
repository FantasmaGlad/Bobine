# PyInstaller spec — BobineBackend + BobineTray. Mode "onedir" autonome : les deux exécutables
# partagent le même dossier de sortie dist/Bobine/ qui est copié tel quel
# dans /usr/lib/bobine/.

import sys
from pathlib import Path

block_cipher = None

# Le serveur figé ne recharge pas les sources et ne lit pas de logs YAML.
# dotenv reste requis à l’import de pydantic-settings, même sans fichier .env.
# Les migrations SQLite sont intégrées à app.database, sans Alembic/Mako.
runtime_excludes = ["yaml", "watchfiles", "alembic", "mako"]

# Chemins relatifs à CE fichier .spec (packaging/linux/ -> repo)
SPEC_DIR = Path(SPECPATH).resolve()
REPO_DIR = SPEC_DIR.parent.parent
BACKEND_DIR = REPO_DIR / "backend"

# Les trois icônes de canal de la barre système sont embarquées à plat à côté de l'exécutable
# (cf. packaging/common/channel.py) ; l'icône du lanceur, elle, vient du paquet (channel.sh).
sys.path.insert(0, str(SPEC_DIR.parent / "common"))
import channel  # noqa: E402

datas = [
    (str(REPO_DIR / "config.toml"), "."),
    *channel.runtime_icon_datas(REPO_DIR),
    # Numéro de version bundlé — lu au
    # runtime par app.utils.version.get_app_version() à côté de l'exécutable,
    # même mécanisme que config.toml ci-dessus.
    (str(REPO_DIR / "VERSION"), "."),
]

frontend_out = REPO_DIR / "frontend" / "out"
if frontend_out.exists():
    datas.append((str(frontend_out), "frontend/out"))

# COMMIT n'existe que sur les builds CI (ci.yml l'écrit juste avant
# `pyinstaller`) — absent lors d'une compilation manuelle locale, auquel cas
# app.utils.version.get_app_commit() retombe sur "unknown".
commit_file = REPO_DIR / "COMMIT"
if commit_file.exists():
    datas.append((str(commit_file), "."))

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]

backend_analysis = Analysis(
    [str(BACKEND_DIR / "run_backend.py")],
    pathex=[str(BACKEND_DIR)],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pystray", "app.desktop", *runtime_excludes],
    cipher=block_cipher,
)

tray_analysis = Analysis(
    [str(BACKEND_DIR / "run_tray.py")],
    pathex=[str(BACKEND_DIR)],
    datas=[],
    hiddenimports=[
        "pystray._xorg",
        "pystray._appindicator",
        "pystray._gtk",
        "pystray._base",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=runtime_excludes,
    cipher=block_cipher,
)

backend_pyz = PYZ(backend_analysis.pure, backend_analysis.zipped_data, cipher=block_cipher)
tray_pyz = PYZ(tray_analysis.pure, tray_analysis.zipped_data, cipher=block_cipher)

# contents_directory="." : désactive le sous-dossier "_internal" introduit
# par défaut depuis PyInstaller 6 — restaure l'arborescence plate attendue
# par app/config.py (ROOT_DIR), app/main.py (frontend_out) et
# app/desktop/tray.py (_load_icon_image) une fois figé.
backend_exe = EXE(
    backend_pyz,
    backend_analysis.scripts,
    [],
    exclude_binaries=True,
    name="BobineBackend",
    console=True,
    contents_directory=".",
)

tray_exe = EXE(
    tray_pyz,
    tray_analysis.scripts,
    [],
    exclude_binaries=True,
    name="BobineTray",
    console=False,
    contents_directory=".",
)

coll = COLLECT(
    backend_exe,
    backend_analysis.binaries,
    backend_analysis.zipfiles,
    backend_analysis.datas,
    tray_exe,
    tray_analysis.binaries,
    tray_analysis.zipfiles,
    tray_analysis.datas,
    # strip=True : PyInstaller embarque sinon libpython et uvloop (extensions C)
    # avec leurs symboles de débogage (libpython ~29 Mo, uvloop ~15,8 Mo).
    # Mesuré sur la 5.0.2 : dossier installé 138 -> 74 Mo, paquet compressé
    # ~46 -> ~31 Mo, et la copie strippée démarre et sert /api/health, le
    # statique et /api/settings. Le strip est appliqué par COLLECT, donc avant
    # toute étape postérieure à PyInstaller (signature, dpkg-deb, hdiutil).
    strip=True,
    upx=False,
    name="Bobine",
)
