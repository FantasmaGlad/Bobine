from ..probe import _get_android_prop
from .fields import Found

_SOC_MEMORY = (
    (("SM8750", "SM8735", "SUN", "SM8650", "PINEAPPLE", "SM8635", "SM8550", "KALAMA"), "LPDDR5X", "8533 MT/s"),
    (("SM8475", "SM8450", "TARO", "CAPE"), "LPDDR5", "6400 MT/s"),
)


def read() -> Found:
    soc = _get_android_prop("ro.soc.model").upper()
    dram = _get_android_prop("ro.boot.dram_type") or _get_android_prop("ro.boot.ddr_type")
    found = {"type": dram.upper()} if dram else {}
    for socs, kind, freq in _SOC_MEMORY:
        if any(s in soc for s in socs):
            return {"type": kind, "freq": freq}
    return found
