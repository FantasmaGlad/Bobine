def projector_candidates(exe_dir, bin_name: str) -> list:
    return [
        exe_dir / bin_name,
        exe_dir / "projector" / "target" / "release" / bin_name,
        exe_dir.parent / "projector" / "target" / "release" / bin_name,
    ]


def first_existing(candidates, exists) -> str | None:
    for candidate in candidates:
        if exists(str(candidate)):
            return str(candidate)
    return None

