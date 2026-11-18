from ..probe import _get_android_prop


def storage_model() -> str:
    bootdevice = (_get_android_prop("ro.boot.bootdevice") or _get_android_prop("ro.boot.boot_devices")).lower()
    soc_model = _get_android_prop("ro.soc.model").upper()
    if "ufshc" in bootdevice:
        if any(s in soc_model for s in ("SM8750", "SM8735", "SUN", "SM8650", "PINEAPPLE")):
            return "Flash UFS 4.0 (256 Go)"
        if any(s in soc_model for s in ("SM8550", "KALAMA", "SM8475")):
            return "Flash UFS 3.1"
        return "Flash UFS"
    return "Flash eMMC 5.1" if "mmc" in bootdevice else ""
