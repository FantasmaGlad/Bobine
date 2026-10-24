# PyInstaller spec — BobineBackend + BobineTray. Un seul spec, deux exécutables partageant le même dossier de
# sortie (mode "onedir" : plus simple à déboguer que "onefile", à reconsidérer une fois
# stabilisé).
#
# Construction (depuis backend/, sur la plateforme cible — PyInstaller ne
# cross-compile PAS : ce spec produit un binaire Windows uniquement s'il
# tourne sur Windows) :
#
#   pyinstaller ../packaging/windows/bobine.spec
#
# Sortie : dist/Bobine/{BobineBackend.exe, BobineTray.exe, config.toml,
# icon.png, frontend/out/, ...}. C'est ce dossier que le script Inno Setup
# (packaging/windows/bobine.iss) copie tel quel dans %ProgramFiles%\Bobine\.

import sys
from pathlib import Path

block_cipher = None

# Le serveur figé ne recharge pas les sources et ne lit pas de logs YAML.
# dotenv reste requis à l’import de pydantic-settings, même sans fichier .env.
# Les migrations SQLite sont intégrées à app.database, sans Alembic/Mako.
runtime_excludes = ["yaml", "watchfiles", "alembic", "mako"]

# Chemins relatifs à CE fichier .spec (backend/../packaging/windows/ -> repo).
SPEC_DIR = Path(SPECPATH).resolve()
REPO_DIR = SPEC_DIR.parent.parent
BACKEND_DIR = REPO_DIR / "backend"

# Canal du build (suffixe de VERSION) : fixe l'icône des exécutables ; les trois icônes de
# canal de la barre système sont embarquées (cf. packaging/common/channel.py).
sys.path.insert(0, str(SPEC_DIR.parent / "common"))
import channel  # noqa: E402

BUILD_CHANNEL = channel.build_channel(REPO_DIR)
ICON_PATH = str(SPEC_DIR / f"bobine-{BUILD_CHANNEL}.ico")

datas = [
    (str(REPO_DIR / "config.toml"), "."),
    # Noms gardés tels quels (PyInstaller ne renomme pas les fichiers de `datas`) —
    # app.desktop.channel_icon.icon_candidates() les cherche à côté de l'exécutable.
    *channel.runtime_icon_datas(REPO_DIR),
    # Même nom d'installation quel que soit le canal : {app}\bobine.ico.
    (channel.stage_icon(Path(ICON_PATH), Path(workpath), "bobine.ico"), "."),
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
    datas=[],  # icon.png déjà copié via backend_analysis dans le même dossier de sortie
    hiddenimports=["pystray._xorg", "pystray._win32", "pystray._darwin", "pystray._base"],
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
# app/desktop/tray.py (_load_icon_image) une fois figé : tout à côté de
# l'exécutable, (pas de sous-dossier à
# connaître en plus).

backend_exe = EXE(
    backend_pyz,
    backend_analysis.scripts,
    [],
    exclude_binaries=True,
    name="BobineBackend",
    console=True,  # Masqué nativement par CREATE_NO_WINDOW dans tray.py ; préserve les flux valides
    contents_directory=".",
    icon=ICON_PATH,
)

tray_exe = EXE(
    tray_pyz,
    tray_analysis.scripts,
    [],
    exclude_binaries=True,
    name="BobineTray",
    console=False,  # pas de fenêtre console pour l'app de bureau au quotidien
    contents_directory=".",
    icon=ICON_PATH,
)

# COLLECT unique : les deux exécutables et leurs dépendances partagées
# atterrissent dans le MÊME dossier dist/Bobine/, comme prévu (Inno Setup
# copie ce dossier tel quel).
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
