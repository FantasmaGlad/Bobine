"""Point d'entrée figé par PyInstaller en `BobineTray.exe` (cf.
`packaging/windows/bobine.spec`). Une sous-commande en premier argument (`bobine status`, `bobine diagnose`...) part
vers la CLI avant tout import de l'icône système ; sinon l'application se lance comme toujours."""

import sys

if __name__ == "__main__":
    from app.cli import COMMANDS

    if len(sys.argv) > 1 and (sys.argv[1] in COMMANDS or sys.argv[1] in ("-h", "--help", "--version")):
        from app.cli import main

        sys.exit(main(sys.argv[1:]))

    from app.desktop.tray import run

    run()
