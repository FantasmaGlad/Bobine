import subprocess

from .common import COMMAND_TIMEOUT_SECONDS, has_battery, logger


def has_lid() -> bool:
    return has_battery()


def prevent_sleep() -> bool:
    try:
        res = subprocess.run(
            ["powercfg", "/query", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION"],
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        return "0x00000000" in res.stdout or " 0 " in res.stdout
    except Exception as e:
        logger.debug(f"Erreur lecture powercfg capot Windows : {e}")
        return False


def set_prevent_sleep(prevent: bool) -> bool:
    try:
        val = "0" if prevent else "1"
        subprocess.run(
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION", val],
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"], check=False, timeout=COMMAND_TIMEOUT_SECONDS)
        return True
    except Exception as e:
        logger.error(f"Erreur écriture powercfg capot Windows : {e}")
        return False
