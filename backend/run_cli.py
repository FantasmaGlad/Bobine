"""Point d'entrée figé en `bobine.exe` sous Windows (cf."""

import sys

from app.cli import main

if __name__ == "__main__":
    sys.exit(main())
