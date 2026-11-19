import logging

logger = logging.getLogger(__name__)


def enumerate_monitors() -> list:
    import ctypes
    from ctypes import wintypes

    from app.desktop.monitors import Monitor

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    try:
        user32.SetProcessDPIAware()
    except Exception as exc:
        logger.debug("_list_monitors_windows : %s", exc)

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    MONITORINFOF_PRIMARY = 1
    found: list[Monitor] = []
    enum_proc_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
    )

    def _callback(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            rect = info.rcMonitor
            found.append(
                Monitor(
                    name=str(info.szDevice),
                    x=int(rect.left),
                    y=int(rect.top),
                    width=int(rect.right - rect.left),
                    height=int(rect.bottom - rect.top),
                    primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
                )
            )
        return True

    user32.EnumDisplayMonitors(None, None, enum_proc_type(_callback), 0)
    return found
