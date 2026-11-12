import uuid

_BOOT_ID = uuid.uuid4().hex


def current_boot_id() -> str:
    return _BOOT_ID
