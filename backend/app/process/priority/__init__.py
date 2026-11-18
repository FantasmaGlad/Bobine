"""Priorité réduite des processus de fond quand le navigateur partage la machine."""
from .policy import shares_machine_with_browser
from .registry import background_priority_popen_kwargs, lower_process_priority

__all__ = ["background_priority_popen_kwargs", "lower_process_priority", "shares_machine_with_browser"]
