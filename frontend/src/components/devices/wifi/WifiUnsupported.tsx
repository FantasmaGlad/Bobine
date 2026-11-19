"use client";

import Icon from "@/components/Icon";
import { openSystemSettings, type SectionProps } from "../common";

interface UnsupportedProps {
  reason?: string;
  systemSettings: boolean;
  notify: SectionProps["notify"];
  t: SectionProps["t"];
}

export default function WifiUnsupported({ reason, systemSettings, notify, t }: UnsupportedProps) {
  return (
    <div className="rl-empty-state">
      <Icon name="wifi_off" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
      <p style={{ margin: 0, fontWeight: 600 }}>{t("devices.wifi.unsupported")}</p>
      {reason && <p className="settings-hint">{reason}</p>}
      {systemSettings && (
        <button type="button" className="btn btn-secondary" style={{ marginTop: "12px" }} onClick={() => openSystemSettings("wifi", notify, t)}>
          <Icon name="settings" size={14} /> {t("devices.wifi.openSettings")}
        </button>
      )}
    </div>
  );
}
