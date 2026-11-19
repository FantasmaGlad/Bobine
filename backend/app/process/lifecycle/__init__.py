"""Cycle de vie des processus : présence d'un PID, arrêt propre sur signal."""
from .registry import install_termination_handler, pid_alive

__all__ = ["install_termination_handler", "pid_alive"]
