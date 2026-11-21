"use client";

import Icon from "@/components/Icon";
import { devicesRequest } from "@/lib/devices/request";
import { type WifiStatus } from "@/lib/devices/types";
import { type SectionProps } from "../shared/section";
import { openSystemSettings } from "../shared/systemSettings";
import { type WifiActions } from "./useWifiActions";

interface ToolbarProps {
  data: WifiStatus;
  can: (key: string) => boolean;
  systemSettings: boolean;
  pending: boolean;
  actions: WifiActions;
  reload: () => Promise<void>;
  notify: SectionProps["notify"];
  t: SectionProps["t"];
}

function CurrentStatus({ data, t }: { data: WifiStatus; t: SectionProps["t"] }) {
  const current = data.current ?? null;
  return (
    <>
      <span className={`status-pill ${current ? "success" : "neutral"}`}>
        <Icon name={current ? "wifi" : "wifi_off"} size={14} />{" "}
        {current ? (current.ssid ? t("devices.wifi.connectedTo", { ssid: current.ssid }) : t("devices.wifi.connectedUnnamed")) : t("devices.wifi.disconnected")}
      </span>
      {current?.ip && <span className="dv-sub">{current.ip}</span>}
      {current && !current.ssid && current.ssid_reason && <span className="dv-sub">{current.ssid_reason}</span>}
      {data.transport && data.transport !== "wifi" && data.transport !== "none" && (
        <span className="dv-sub">{t("devices.wifi.otherTransport", { transport: data.transport })}</span>
      )}
    </>
  );
}

export default function WifiToolbar({ data, can, systemSettings, pending, actions, reload, notify, t }: ToolbarProps) {
  return (
    <div className="dv-toolbar">
      <CurrentStatus data={data} t={t} />
      <div className="rl-toolbar-spacer" />
      {can("wifi_scan") && data.enabled && (
        <button type="button" className="btn btn-secondary" disabled={actions.busy} onClick={async () => { await devicesRequest("/wifi/scan", { body: {} }); setTimeout(() => { void reload(); }, 2500); }}>
          <Icon name="refresh" size={14} /> {t("devices.wifi.scan")}
        </button>
      )}
      {can("wifi_power") && (
        <button type="button" className="btn btn-secondary" disabled={actions.busy || pending} onClick={() => actions.power(!data.enabled)}>
          <Icon name="power_settings_new" size={14} /> {data.enabled ? t("devices.wifi.turnOff") : t("devices.wifi.turnOn")}
        </button>
      )}
      {systemSettings && (
        <button type="button" className="btn btn-secondary" onClick={() => openSystemSettings("wifi", notify, t)}>
          <Icon name="settings" size={14} /> {t("devices.wifi.openSettings")}
        </button>
      )}
    </div>
  );
}
