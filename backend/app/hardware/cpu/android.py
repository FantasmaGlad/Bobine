import logging
import os

from ..probe import _get_android_prop

logger = logging.getLogger(__name__)

_SOC_NAME_MAP: dict[str, str] = {
    "SM8750": "Qualcomm Snapdragon 8 Elite",
    "SM8735": "Qualcomm Snapdragon 8 Elite",
    "SM8735P": "Qualcomm Snapdragon 8 Elite",
    "SUN": "Qualcomm Snapdragon 8 Elite",
    "SM8650": "Qualcomm Snapdragon 8 Gen 3",
    "PINEAPPLE": "Qualcomm Snapdragon 8 Gen 3",
    "SM8635": "Qualcomm Snapdragon 8s Gen 3",
    "CLITI": "Qualcomm Snapdragon 8s Gen 3",
    "SM8550": "Qualcomm Snapdragon 8 Gen 2",
    "KALAMA": "Qualcomm Snapdragon 8 Gen 2",
    "SM8475": "Qualcomm Snapdragon 8+ Gen 1",
    "CAPE": "Qualcomm Snapdragon 8+ Gen 1",
    "SM8450": "Qualcomm Snapdragon 8 Gen 1",
    "TARO": "Qualcomm Snapdragon 8 Gen 1",
    "SM8350": "Qualcomm Snapdragon 888",
    "LAHAINA": "Qualcomm Snapdragon 888",
    "SM8250": "Qualcomm Snapdragon 865",
    "KONA": "Qualcomm Snapdragon 865",
    "SM8150": "Qualcomm Snapdragon 855",
    "SM7675": "Qualcomm Snapdragon 7+ Gen 3",
    "SM7550": "Qualcomm Snapdragon 7 Gen 3",
    "SM7475": "Qualcomm Snapdragon 7+ Gen 2",
    "SM7450": "Qualcomm Snapdragon 7 Gen 1",
    "SM7325": "Qualcomm Snapdragon 778G",
    "SM7250": "Qualcomm Snapdragon 765G",
    "SM6450": "Qualcomm Snapdragon 6 Gen 1",
    "SM6375": "Qualcomm Snapdragon 695",
    "SM4450": "Qualcomm Snapdragon 4 Gen 2",
    "TENSOR G4": "Google Tensor G4",
    "ZUMA PRO": "Google Tensor G4",
    "TENSOR G3": "Google Tensor G3",
    "ZUMA": "Google Tensor G3",
    "TENSOR G2": "Google Tensor G2",
    "CLOUDRIPPER": "Google Tensor G2",
    "TENSOR": "Google Tensor G1",
    "WHITECAP": "Google Tensor G1",
    "MT6991": "MediaTek Dimensity 9400",
    "MT6989": "MediaTek Dimensity 9300",
    "MT6985": "MediaTek Dimensity 9200",
    "MT6983": "MediaTek Dimensity 9000",
    "MT6897": "MediaTek Dimensity 8300",
    "MT6895": "MediaTek Dimensity 8100",
}


def _soc_file(name: str) -> str:
    path = f"/sys/devices/soc0/{name}"
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception as exc:
        logger.debug("get_cpu_model_name : %s", exc)
        return ""


def cpu_name() -> str:
    soc_model = _get_android_prop("ro.soc.model").strip()
    platform_code = _get_android_prop("ro.board.platform").strip()
    family, machine = _soc_file("family"), _soc_file("machine")
    for candidate in (soc_model.upper(), platform_code.upper(), machine.upper()):
        if candidate in _SOC_NAME_MAP:
            return _SOC_NAME_MAP[candidate]
    if soc_model:
        if soc_model.upper().startswith("SM") or "SNAPDRAGON" in family.upper():
            return f"Qualcomm Snapdragon ({soc_model})"
        if soc_model.upper().startswith("MT"):
            return f"MediaTek Dimensity ({soc_model})"
        return f"SoC {soc_model}"
    return f"Qualcomm Snapdragon ({platform_code})" if platform_code else ""
