from .common import output


def name() -> str | None:
    for line in output(["system_profiler", "SPDisplaysDataType"], 2).splitlines():
        if line.strip().startswith("Chipset Model:"):
            return line.split(":", 1)[1].strip()
    return None
