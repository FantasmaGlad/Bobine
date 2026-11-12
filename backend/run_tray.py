"""Point d'entrée figé par PyInstaller en `BobineTray.exe`."""

import sys

_CLI_OPTIONS = {
    "-h", "--help", "--version", "--host", "--port", "--json", "-v", "-vv", "--verbose", "-q", "--quiet", "--no-color",
}


def _is_cli_invocation(argv: list[str]) -> bool:
    if not argv:
        return False
    from app.cli import COMMANDS

    return any(arg in COMMANDS or arg in _CLI_OPTIONS for arg in argv)


if __name__ == "__main__":
    if _is_cli_invocation(sys.argv[1:]):
        from app.cli import main

        sys.exit(main(sys.argv[1:]))

    from app.desktop.tray import run

    run()
