# PyInstaller spec — BobineBackend + BobineTray (PortabiliteCrossPlatformX
# Lot 2 — Linux de bureau .deb). Mode "onedir" autonome : les deux exécutables
# partagent le même dossier de sortie dist/Bobine/ qui est copié tel quel
# dans /usr/lib/bobine/.

import sys
from pathlib import Path

block_cipher = None

# Chemins relatifs à CE fichier .spec (packaging/linux/ -> repo)
SPEC_DIR = Path(SPECPATH).resolve()
REPO_DIR = SPEC_DIR.parent.parent
BACKEND_DIR = REPO_DIR / "backend"

datas = [
    (str(REPO_DIR / "config.toml"), "."),
    (str(REPO_DIR / "Assets" / "Images" / "logo_bobine_icon.png"), "."),
]

frontend_out = REPO_DIR / "frontend" / "out"
if frontend_out.exists():
    datas.append((str(frontend_out), "frontend/out"))

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
    excludes=["pystray", "app.desktop"],
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
    strip=False,
    upx=False,
    name="Bobine",
)
