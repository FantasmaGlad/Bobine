"use client";

import Icon from "@/components/Icon";
import { type Capabilities } from "@/lib/devices/types";
import { openSystemSettings, type SectionProps } from "../common";

export function AudioUnsupported({ reason, t }: { reason?: string; t: SectionProps["t"] }) {
  return (
    <div className="rl-empty-state">
      <Icon name="volume_off" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
      <p style={{ margin: 0, fontWeight: 600 }}>{t("devices.audio.unsupported")}</p>
      {reason && <p className="settings-hint">{reason}</p>}
    </div>
  );
}

export function NoDefaultSwitchNote({ caps, notify, t }: { caps: Capabilities; notify: SectionProps["notify"]; t: SectionProps["t"] }) {
  return (
    <div className="dv-note">
      <Icon name="info" size={16} />
      <span>{caps.audio_set_default?.reason || t("devices.audio.noDefaultSwitch")}</span>
      {caps.system_settings?.supported && (
        <button type="button" className="btn btn-secondary" onClick={() => openSystemSettings("sound", notify, t)}>
          <Icon name="tune" size={14} /> {t("devices.audio.openSoundSettings")}
        </button>
      )}
    </div>
  );
}
