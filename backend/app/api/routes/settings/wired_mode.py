"""Mode d'affichage de l'écran câblé (étendu, miroir, seul) : réglage et valeur effective."""

from sqlalchemy.orm import Session

from app.utils.deployment import (
    get_deployment_profile,
)
from app.utils.display_state import (
    DEFAULT_DISPLAY_MODE_SETTING,
    VALID_DISPLAY_MODE_SETTINGS,
    effective_wired_display_mode,
    get_hardware_state,
)

from .core import _get_db_value


def get_display_mode_setting(db: Session) -> str:
    value = _get_db_value(db, "display_mode_setting") or DEFAULT_DISPLAY_MODE_SETTING
    return value if value in VALID_DISPLAY_MODE_SETTINGS else DEFAULT_DISPLAY_MODE_SETTING


def get_effective_wired_display_mode(db: Session) -> str:
    """Mode d'affichage câblé effectif : forçage admin, sinon
    dérivé des écrans externes réellement connectés. Sans rapport matériel :
    `dual_screen` sur Android (tablette = pupitre tactile, comportement
    historique), `headless` ailleurs."""
    default = "dual_screen" if get_deployment_profile() == "android" else "headless"
    return effective_wired_display_mode(
        get_display_mode_setting(db), get_hardware_state().external_count, default
    )
