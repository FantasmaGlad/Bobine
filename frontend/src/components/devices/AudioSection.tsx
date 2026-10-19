"use client";

import { useState } from "react";
import Icon from "@/components/Icon";
import { audioKindIcon, devicesRequest, type AudioDevice, type AudioListing } from "@/lib/devicesApi";
import { errorText, openSystemSettings, useDevicesResource, type SectionProps } from "./common";

export default function AudioSection({ caps, refreshKey, notify, t }: SectionProps) {
  const { data, error, loading, reload } = useDevicesResource<AudioListing>("/audio", refreshKey);
  const [draft, setDraft] = useState<Record<string, number>>({});

  const call = async (path: string, body: unknown, okMessage?: string) => {
    const result = await devicesRequest(path, { body });
    if (result.ok) {
      if (okMessage) notify(okMessage, "success");
      await reload();
    } else {
      notify(errorText(result.error, t), "error");
    }
  };

  const commitVolume = async (id: string, percent: number) => {
    await call("/audio/volume", { id, volume: percent / 100 });
    setDraft((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });
  };

  const canDefault = caps.audio_set_default?.supported;
  const canVolume = caps.audio_set_volume?.supported;

  if (loading) return <div className="rl-center-note">{t("devices.loading")}</div>;
  if (error) return <div className="rl-center-note">{errorText(error, t)}</div>;
  if (!data?.supported) {
    return (
      <div className="rl-empty-state">
        <Icon name="volume_off" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
        <p style={{ margin: 0, fontWeight: 600 }}>{t("devices.audio.unsupported")}</p>
        {data?.reason && <p className="settings-hint">{data.reason}</p>}
      </div>
    );
  }

  const devices = data.devices ?? [];
  return (
    <div className="dv-section">
      {!canDefault && (
        <div className="dv-note">
          <Icon name="info" size={16} />
          <span>{caps.audio_set_default?.reason || t("devices.audio.noDefaultSwitch")}</span>
          {caps.system_settings?.supported && (
            <button type="button" className="btn btn-secondary" onClick={() => openSystemSettings("sound", notify, t)}>
              <Icon name="tune" size={14} /> {t("devices.audio.openSoundSettings")}
            </button>
          )}
        </div>
      )}
      {devices.length === 0 ? (
        <p className="rl-empty-note">{t("devices.audio.none")}</p>
      ) : (
        <div className="dv-list">
          {devices.map((device: AudioDevice) => {
            const volume = draft[device.id] ?? Math.round((device.volume ?? 0) * 100);
            return (
              <div key={device.id} className={`dv-row ${device.is_default ? "active" : ""} ${device.available ? "" : "off"}`}>
                <span className="dv-icon"><Icon name={audioKindIcon(device.kind)} size={22} /></span>
                <span className="dv-text">
                  <span className="dv-title">
                    {device.name}
                    {device.is_default && <span className="dv-badge">{t("devices.audio.default")}</span>}
                  </span>
                  <span className="dv-sub">
                    {t(`devices.audio.kind.${device.kind}`)}
                    {device.manufacturer ? ` · ${device.manufacturer}` : ""}
                  </span>
                </span>
                {canVolume && device.volume !== null && (
                  <span className="dv-volume">
                    <button
                      type="button"
                      className="dv-icon-btn"
                      title={device.muted ? t("devices.audio.unmute") : t("devices.audio.mute")}
                      onClick={() => call("/audio/volume", { id: device.id, muted: !device.muted })}
                    >
                      <Icon name={device.muted ? "volume_off" : "volume_up"} size={20} />
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={volume}
                      aria-label={t("devices.audio.volume")}
                      onChange={(e) => setDraft({ ...draft, [device.id]: Number(e.target.value) })}
                      onMouseUp={() => commitVolume(device.id, volume)}
                      onTouchEnd={() => commitVolume(device.id, volume)}
                      onKeyUp={() => commitVolume(device.id, volume)}
                    />
                    <span className="dv-value">{volume} %</span>
                  </span>
                )}
                {canDefault && !device.is_default && (
                  <button type="button" className="btn btn-secondary" onClick={() => call("/audio/default", { id: device.id }, t("devices.audio.defaultSet"))}>
                    {t("devices.audio.use")}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
