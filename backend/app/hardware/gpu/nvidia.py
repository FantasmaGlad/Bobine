from .common import output


def read() -> tuple[float | None, float | None, str | None]:
    fields = "--query-gpu=utilization.gpu,temperature.gpu,name"
    parts = [p.strip() for p in output(["nvidia-smi", fields, "--format=csv,noheader,nounits"]).strip().splitlines()[0].split(",")]
    if len(parts) < 2:
        return None, None, None
    return float(parts[0]), float(parts[1]), parts[2] if len(parts) >= 3 else None
