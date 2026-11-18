GOP = ["-g", "60"]
SOFTWARE_TIER = {
    "name": "software_libx264",
    "encoder_name": "libx264",
    "hw_in": [],
    "enc_args": ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-threads", "0", "-pix_fmt", "yuv420p", *GOP, "-keyint_min", "60"],
}


def tier(name: str, encoder: str, hw_in: list[str], enc_args: list[str]) -> dict:
    return {"name": name, "encoder_name": encoder, "hw_in": hw_in, "enc_args": [*enc_args, *GOP]}


def hardware_tiers(prefix: str, encoder: str, hw_in: list[str], enc_args: list[str], hybrid_args: list[str] | None = None) -> list[dict]:
    """Décodage et encodage matériels, puis encodage matériel seul, puis logiciel."""
    return [tier(f"{prefix}_full", encoder, hw_in, enc_args),
            tier(f"{prefix}_hybrid", encoder, [], hybrid_args or enc_args),
            dict(SOFTWARE_TIER)]
