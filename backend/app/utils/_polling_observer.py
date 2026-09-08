"""Repli du profil Android pour la surveillance de dossier (cf.
docs/PortabiliteAndroid.md §3.1/§9, docs/plan-implementation-android.md Lot 0) :
le paquet `watchdog` n'a aucune distribution Android (le noyau expose bien
inotify, mais aucun wheel du paquet PyPI n'existe pour cette cible). Ce module
n'est importé que si `watchdog` est absent — voir `app/utils/watcher.py`.

Implémente le sous-ensemble exact de l'API `watchdog.observers.Observer` /
`watchdog.events.FileSystemEventHandler` utilisé par `watcher.py`
(`schedule`, `start`, `stop`, `join`, `on_created`, `on_moved`,
`event.is_directory`, `event.src_path`, `event.dest_path`) — pas une
réimplémentation générale de watchdog. Un polling périodique (pas d'inotify
natif) : suffisant ici, l'import de dossier surveillé n'est pas un chemin
sensible à la latence.
"""

import os
import threading
import time


class _Event:
    def __init__(self, path: str, is_directory: bool):
        self.src_path = path
        self.dest_path = path
        self.is_directory = is_directory


class FileSystemEventHandler:
    """Classe de base — les sous-classes de watcher.py redéfinissent
    on_created/on_moved ; ces implémentations par défaut ne sont là que pour
    la parité d'API avec watchdog.events.FileSystemEventHandler."""

    def on_created(self, event):
        pass

    def on_moved(self, event):
        pass


class PollingObserver:
    """Remplace `watchdog.observers.Observer` : scrute chaque dossier
    surveillé à intervalle régulier plutôt que de recevoir des événements
    inotify. Chaque nouvelle entrée (fichier ou dossier) déclenche
    `on_created` — suffisant pour les handlers de watcher.py, qui ne
    distinguent pas réellement "créé" de "déplacé" dans leur logique."""

    POLL_INTERVAL_SECONDS = 2.0

    def __init__(self):
        self._watches: list[tuple[object, str]] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def schedule(self, handler, path: str, recursive: bool = False):
        # `recursive` ignoré : tous les usages actuels de watcher.py
        # surveillent un seul niveau (recursive=False côté appelant).
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
