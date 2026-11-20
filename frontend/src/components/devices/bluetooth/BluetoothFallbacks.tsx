"use client";

import Icon from "@/components/Icon";
import { type SectionProps } from "../shared/section";
import { type BluetoothCall } from "./useBluetoothCall";

export function BluetoothUnsupported({ reason, t }: { reason?: string; t: SectionProps["t"] }) {
  return (
    <div className="rl-empty-state">
      <Icon name="bluetooth_disabled" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
      <p style={{ margin: 0, fontWeight: 600 }}>{t("devices.bluetooth.unsupported")}</p>
      {reason && <p className="settings-hint">{reason}</p>}
    </div>
  );
}

export function BluetoothPermission({ message, call, t }: { message?: string | null; call: BluetoothCall; t: SectionProps["t"] }) {
  return (
    <div className="dv-section">
      <div className="dv-note dv-note--strong">
        <Icon name="bluetooth_searching" size={18} />
        <span>{message || t("devices.bluetooth.permissionBody")}</span>
        <button type="button" className="btn btn-primary" onClick={() => call("/bluetooth/permission")}>
          <Icon name="check" size={14} /> {t("devices.bluetooth.permissionButton")}
        </button>
      </div>
    </div>
  );
}
