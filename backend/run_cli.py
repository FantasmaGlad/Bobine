"""Point d'entrée figé en `bobine.exe` sous Windows (cf. `packaging/windows/bobine.spec`) : exécutable console, à la
différence de `BobineTray.exe`, pour que la commande `bobine` affiche ses résultats dans le terminal."""

import sys

from app.cli import main

if __name__ == "__main__":
    sys.exit(main())
