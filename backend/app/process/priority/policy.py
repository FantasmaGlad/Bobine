def shares_machine_with_browser() -> bool:
    """Vrai sur les profils où le navigateur d'administration tourne sur la même machine que le backend."""
    from app.utils.deployment import get_deployment_profile

    return get_deployment_profile() in ("windows", "macos", "linux-desktop")
