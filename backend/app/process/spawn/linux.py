from .posix import SUFFIX, hidden_console_kwargs, restrict_directory

__all__ = ["SUFFIX", "hidden_console_kwargs", "restrict_directory", "tied_to_parent_kwargs"]


def _parent_death_signal() -> None:
    import ctypes
    import signal

    ctypes.CDLL(None).prctl(1, signal.SIGTERM)


def tied_to_parent_kwargs() -> dict:
    return {"preexec_fn": _parent_death_signal}
