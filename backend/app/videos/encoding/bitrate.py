def get_target_bitrate(width: int | None, height: int | None) -> str:
    """Débit cible selon la résolution source, sans réduction de résolution."""
    pixels = (width or 1920) * (height or 1080)
    if pixels >= 3840 * 2160 * 0.8:
        return "28M"
    if pixels >= 2560 * 1440 * 0.8:
        return "14M"
    return "6M"
