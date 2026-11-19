"""Bureau par système : écran maintenu allumé, kiosque, moniteurs, intégration au lancement."""
from .registry import current, for_name, system_name

__all__ = ["current", "for_name", "system_name"]
