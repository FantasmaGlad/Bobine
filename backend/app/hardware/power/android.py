from ..cpu import get_cpu_percent


def battery_power() -> float | None:
    from android.content import Context, Intent, IntentFilter
    from android.os import BatteryManager
    from com.chaquo.python import Python
    app_ctx = Python.getPlatform().getApplication()
    bm = app_ctx.getSystemService(Context.BATTERY_SERVICE)
    filt = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
    intent = app_ctx.registerReceiver(None, filt)
    if not intent:
        return None
    plugged = intent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)
    status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
    voltage_mv = intent.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1)
    current_ua = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
    if current_ua == -2147483648:
        current_ua = 0

    cpu_pct = get_cpu_percent()

    if plugged > 0 or status in (BatteryManager.BATTERY_STATUS_CHARGING, BatteryManager.BATTERY_STATUS_FULL):
        active_w = 3.2 + (cpu_pct / 100.0) * 5.0

        if status == BatteryManager.BATTERY_STATUS_CHARGING and current_ua != 0 and abs(current_ua) < 20_000_000:
            v = (voltage_mv / 1000.0) if voltage_mv > 0 else 4.2
            charge_w = (abs(current_ua) / 1_000_000.0) * v
            return round(min(120.0, max(1.0, charge_w + active_w)), 1)
        return round(min(60.0, max(1.5, active_w)), 1)

    if current_ua != 0 and abs(current_ua) < 20_000_000 and voltage_mv > 0:
        watts = (abs(current_ua) / 1_000_000.0) * (voltage_mv / 1000.0)
        if 0.5 <= watts <= 60.0:
            return round(watts, 1)

    return round(2.8 + (cpu_pct / 100.0) * 4.5, 1)
