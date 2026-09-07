# PyInstaller spec — BobineBackend + BobineTray (PortabiliteCrossPlatformX
# Lot 3 — macOS). Produit un unique bundle `Bobine.app` (via BUNDLE())
# contenant les deux exécutables *onedir* dans `Contents/MacOS/`.
#
# Construction (SUR UNE VRAIE MACHINE macOS — PyInstaller ne cross-compile
# pas, ce spec ne peut pas produire de bundle macOS depuis Linux/Windows) :
#
#   cd backend && pyinstaller ../packaging/macos/bobine.spec
#
# Sortie : dist/Bobine.app. Contrairement à Windows/Linux (contents_directory
# = "." pour une arborescence plate), macOS `BUNDLE()` relocalise les
# `datas` (config.toml, icône, frontend/out/) sous `Contents/Resources/` et
# ne laisse que les binaires dans `Contents/MacOS/` — pris en compte par
# `app/config.py::ROOT_DIR` et `app/main.py::frontend_out` (branches
# `platform.system() == "Darwin"`, cf.
# docs/plan-implementation-portabilite-crossplatformx.md §4).
#
# NON TESTÉ sur une vraie machine macOS — écrit d'après :
#   - la documentation officielle PyInstaller (BUNDLE(), Info.plist,
#     runtime-information.html) ;
#   - le comportement documenté de `pystray._darwin` (AppKit/pyobjc) ;
# à valider au premier passage du job CI `macos-build`
# (.github/workflows/ci.yml) et lors d'un test manuel sur Mac réel.

import sys
from pathlib import Path

block_cipher = None

# Chemins relatifs à CE fichier .spec (packaging/macos/ -> repo)
SPEC_DIR = Path(SPECPATH).resolve()
REPO_DIR = SPEC_DIR.parent.parent
BACKEND_DIR = REPO_DIR / "backend"
ICON_PATH = str(SPEC_DIR / "bobine.icns")

# Numéro de version du bundle (réf. mission "canal Stable/Bêta") — lu
# dynamiquement depuis VERSION, jamais recopié en dur ici (c'était le cas
# avant ce lot : BUNDLE() et Info.plist annonçaient "3.0.0" quelle que soit
# la version réellement construite, découvert en même temps que le bug
# analogue sur DEBIAN/control). La CI écrit VERSION avec le suffixe "-beta"
# avant PyInstaller pour les builds du canal Bêta (cf. ci.yml).
APP_VERSION = (REPO_DIR / "VERSION").read_text(encoding="utf-8").strip()

datas = [
    (str(REPO_DIR / "config.toml"), "."),
    (str(REPO_DIR / "Assets" / "Images" / "logo_bobine_icon.png"), "."),
    # Numéro de version bundlé (réf. mission "canal Stable/Bêta") — relocalisé
    # sous Contents/Resources/ comme config.toml ci-dessus, lu au runtime par
    # app.utils.version.get_app_version() (ROOT_DIR y pointe déjà sur macOS).
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
    excludes=["pystray", "app.desktop"],  # inutiles dans BobineBackend
    cipher=block_cipher,
)

# hiddenimports pystray/pyobjc sur macOS : le backend `_darwin` de pystray
# n'est pas détecté par l'analyse statique de PyInstaller (sélection au
# runtime via sys.platform dans pystray/__init__.py::backend()) — sans
# cette liste explicite, `pystray._darwin` et les modules pyobjc/AppKit
# sous-jacents seraient absents du bundle figé (recherche
# PortabiliteCrossPlatformX Lot 3, cf. plan §4).
tray_analysis = Analysis(
    [str(BACKEND_DIR / "run_tray.py")],
    pathex=[str(BACKEND_DIR)],
    datas=[],  # icône déjà copiée via backend_analysis dans le même bundle
    hiddenimports=[
        "pystray._darwin",
        "pystray._base",
        "pystray._util",
        "AppKit",
        "Foundation",
        "objc",
        "PyObjCTools.MachSignals",
    ],
    hookspath=[],
    runtime_hooks=[],
    cipher=block_cipher,
)

backend_pyz = PYZ(backend_analysis.pure, backend_analysis.zipped_data, cipher=block_cipher)
tray_pyz = PYZ(tray_analysis.pure, tray_analysis.zipped_data, cipher=block_cipher)

# Sur macOS, EXE() ne prend PAS `contents_directory` (spécifique Windows/
# Linux) : la relocalisation Contents/MacOS vs Contents/Resources est gérée
# par BUNDLE() plus bas, pas par EXE() lui-même.
backend_exe = EXE(
    backend_pyz,
    backend_analysis.scripts,
    [],
    exclude_binaries=True,
    name="BobineBackend",
    console=True,
)

tray_exe = EXE(
    tray_pyz,
    tray_analysis.scripts,
    [],
    exclude_binaries=True,
    name="BobineTray",
    console=False,
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

# `tray_exe` passé AVANT `coll` : BUNDLE() choisit `CFBundleExecutable` en
# prenant le premier binaire EXECUTABLE trouvé dans la table des matières
# fusionnée — sans cet ordre explicite, ce serait `BobineBackend` par
# défaut (mauvais choix : c'est BobineTray, pas le backend, qui doit être
# lancé par Finder/Dock/LaunchAgent ; il démarre lui-même BobineBackend en
# process enfant, cf. app/desktop/tray.py::_backend_command). Les deux
# exécutables restent côte à côte dans Contents/MacOS/ quel que soit cet
# ordre — la recherche de process frère dans tray.py n'en dépend donc pas.
app_bundle = BUNDLE(
    tray_exe,
    coll,
    name="Bobine.app",
    icon=ICON_PATH,
    bundle_identifier="com.bobine.app",
    version=APP_VERSION,
    info_plist={
        "CFBundleName": "Bobine",
        "CFBundleDisplayName": "Bobine",
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleIconFile": "bobine.icns",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        # Masque l'icône du Dock/le sélecteur d'applications : Bobine est
        # une app de barre de menus, pas une fenêtre classique (CDC §7.2).
        # ATTENTION (découverte recherche, non vérifiée sur Mac réel) : un
        # bug récurrent du bootloader PyInstaller (TransformProcessType,
        # issues #1917/#2075/#3516/#6471) peut faire réapparaître l'icône
        # Dock malgré ce réglage — à vérifier explicitement au premier test
        # manuel (cf. plan §4).
        "LSUIElement": True,
    },
)
