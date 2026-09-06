"""Point d'entrée figé par PyInstaller en `BobineTray.exe` (cf.
`packaging/windows/bobine.spec`)."""

from app.desktop.tray import run

if __name__ == "__main__":
    run()
