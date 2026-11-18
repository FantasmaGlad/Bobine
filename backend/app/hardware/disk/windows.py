from .command import first_line


def storage_model() -> str:
    return first_line(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_DiskDrive).Model"], 2, str.strip)
