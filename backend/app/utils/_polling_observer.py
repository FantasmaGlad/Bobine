"""Repli du profil Android pour la surveillance de dossier (voir docs/ARCHITECTURE.md §3.1) : le paquet `watchdog` n'a aucune distribution Android (le noyau expose bien inotify, mais aucun wheel du paquet PyPI n'existe pour cette cible)."""

import os
import threading


class _Event:
    def __init__(self, path: str, is_directory: bool):
        self.src_path = path
        self.dest_path = path
        self.is_directory = is_directory


class FileSystemEventHandler:
    """Classe de base — les sous-classes de watcher.py redéfinissent on_created/on_moved ; ces implémentations par défaut ne sont là que pour la parité d'API avec watchdog.events.FileSystemEventHandler."""

    def on_created(self, event):
        pass

    def on_moved(self, event):
        pass


class PollingObserver:
    """Remplace `watchdog.observers.Observer` : scrute chaque dossier surveillé à intervalle régulier plutôt que de recevoir des événements inotify."""

    POLL_INTERVAL_SECONDS = 2.0

    def __init__(self):
        self._watches: list[tuple[object, str]] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def schedule(self, handler, path: str, recursive: bool = False):
        self._watches.append((handler, path))

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def join(self):
        if self._thread:
            self._thread.join()

    def _run(self):
        seen: dict[str, set[str]] = {path: set(os.listdir(path)) for _, path in self._watches}
        while not self._stop_event.is_set():
            for handler, path in self._watches:
                try:
                    current = set(os.listdir(path))
                except OSError:
                    continue
                for name in current - seen.get(path, set()):
                    full_path = os.path.join(path, name)
                    is_dir = os.path.isdir(full_path)
                    handler.on_created(_Event(full_path, is_dir))
                seen[path] = current
            self._stop_event.wait(self.POLL_INTERVAL_SECONDS)
