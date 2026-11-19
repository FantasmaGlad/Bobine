import os
import signal


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def install_termination_handler(handler) -> None:
    try:
        signal.signal(signal.SIGTERM, handler)
    except (ValueError, OSError):
        pass
