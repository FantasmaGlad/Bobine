"""Lancement des programmes annexes : nom de l'exécutable, console, lien avec le processus parent."""
from .registry import executable_name, hidden_console_kwargs, restrict_directory, tied_to_parent_kwargs

__all__ = ["executable_name", "hidden_console_kwargs", "restrict_directory", "tied_to_parent_kwargs"]
