"use client";

import Icon from "@/components/Icon";
import { type BluetoothStatus } from "@/lib/devices/types";
import { openSystemSettings, type SectionProps } from "../common";
import { type BluetoothCall } from "./useBluetoothCall";

interface ToolbarProps {
  data: BluetoothStatus;
  can: (key: string) => boolean;
  systemSettings: boolean;
  discovering: boolean;
  busy: boolean;
  call: BluetoothCall;
  notify: SectionProps["notify"];
  t: SectionProps["t"];
}

export default function BluetoothToolbar({ data, can, systemSettings, discovering, busy, call, notify, t }: ToolbarProps) {
  return (
    <div className="dv-toolbar">
      <span className={`status-pill ${data.powered ? "success" : "neutral"}`}>
        <Icon name={data.powered ? "bluetooth" : "bluetooth_disabled"} size={14} /> {data.powered ? t("devices.bluetooth.on") : t("devices.bluetooth.off")}
      </span>
      {data.adapter_name && <span className="dv-sub">{data.adapter_name}</span>}
      <div className="rl-toolbar-spacer" />
      {can("bluetooth_power") && (
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => call("/bluetooth/power", { on: !data.powered })}>
          <Icon name="power_settings_new" size={14} /> {data.powered ? t("devices.bluetooth.turnOff") : t("devices.bluetooth.turnOn")}
        </button>
      )}
      {can("bluetooth_scan") && data.powered && (
        <button type="button" className={`btn ${discovering ? "btn-primary" : "btn-secondary"}`} disabled={busy} onClick={() => call("/bluetooth/scan", { on: !discovering })}>
          <Icon name="bluetooth_searching" size={14} className={discovering ? "olc-spin" : ""} /> {discovering ? t("devices.bluetooth.stopScan") : t("devices.bluetooth.scan")}
        </button>
      )}
      {systemSettings && (
        <button type="button" className="btn btn-secondary" onClick={() => openSystemSettings("bluetooth", notify, t)}>
          <Icon name="settings" size={14} /> {t("devices.bluetooth.openSettings")}
        </button>
      )}
    </div>
  );
}
