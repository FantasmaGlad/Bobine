import sys
from pathlib import Path

block_cipher = None

runtime_excludes = ["yaml", "watchfiles", "alembic", "mako"]

SPEC_DIR = Path(SPECPATH).resolve()
REPO_DIR = SPEC_DIR.parent.parent
BACKEND_DIR = REPO_DIR / "backend"

sys.path.insert(0, str(SPEC_DIR.parent / "common"))
import channel  # noqa: E402

datas = [
    (str(REPO_DIR / "config.toml"), "."),
    *channel.runtime_icon_datas(REPO_DIR),
    (str(REPO_DIR / "VERSION"), "."),
]

frontend_out = REPO_DIR / "frontend" / "out"
if frontend_out.exists():
    datas.append((str(frontend_out), "frontend/out"))

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
    strip=True,
    upx=False,
    name="Bobine",
)
