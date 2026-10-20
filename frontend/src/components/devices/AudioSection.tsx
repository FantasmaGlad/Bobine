"use client";

import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { audioDisplayName, audioKindIcon, devicesRequest, type AudioDevice, type AudioListing } from "@/lib/devicesApi";
import AudioDetailSheet from "./AudioDetailSheet";
import { errorText, openSystemSettings, useDevicesResource, useFocusFlash, type SectionProps } from "./common";

export default function AudioSection({ caps, refreshKey, notify, t, focusId, focusNonce }: SectionProps) {
  const { data, error, loading, reload } = useDevicesResource<AudioListing>("/audio", refreshKey);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [openId, setOpenId] = useState<string | null>(null);
  const [showHidden, setShowHidden] = useState(false);

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

  // Raccourci depuis la carte : ouvre directement le détail de la sortie visée.
  useEffect(() => {
    if (focusId && data?.devices?.some((d) => d.id === focusId)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- ouverture demandée par un raccourci externe (carte)
      setOpenId(focusId);
    }
  }, [focusId, focusNonce, data]);
  useFocusFlash(focusId, focusNonce, !!data?.supported);

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

  const all = data.devices ?? [];
  const devices = all.filter((d) => !d.hidden);
  const hiddenDevices = all.filter((d) => d.hidden);
  const opened = all.find((d) => d.id === openId) ?? null;
  const stop = (e: React.SyntheticEvent) => e.stopPropagation();

  const renderRow = (device: AudioDevice) => {
    const volume = draft[device.id] ?? Math.round((device.volume ?? 0) * 100);
    const open = () => setOpenId(device.id);
    return (
      <div
        key={device.id}
        role="button"
        tabIndex={0}
        data-focus-id={device.id}
        aria-label={t("devices.audio.openDetail", { name: audioDisplayName(device) })}
        className={`dv-row glass-interactive dv-row--click ${device.is_default ? "active" : ""} ${openId === device.id ? "is-selected" : ""} ${device.available ? "" : "off"}`}
        onClick={open}
        onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); open(); } }}
      >
        <span className="dv-icon"><Icon name={audioKindIcon(device.kind)} size={22} /></span>
        <span className="dv-text">
          <span className="dv-title">
            {audioDisplayName(device)}
            {device.is_default && <span className="dv-badge">{t("devices.audio.default")}</span>}
          </span>
          <span className="dv-sub">
            {t(`devices.audio.kind.${device.kind}`)}
            {device.manufacturer ? ` · ${device.manufacturer}` : ""}
            {device.alias ? ` · ${device.name}` : ""}
          </span>
        </span>
        {canVolume && device.volume !== null && (
          <span className="dv-volume" onClick={stop}>
            <button
              type="button"
              className="dv-icon-btn"
              title={device.muted ? t("devices.audio.unmute") : t("devices.audio.mute")}
              onClick={(e) => { stop(e); void call("/audio/volume", { id: device.id, muted: !device.muted }); }}
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
          <button type="button" className="btn btn-secondary" onClick={(e) => { stop(e); void call("/audio/default", { id: device.id }, t("devices.audio.defaultSet")); }}>
            {t("devices.audio.use")}
          </button>
        )}
        <span className="dv-chevron" aria-hidden="true"><Icon name="chevron_right" size={20} /></span>
      </div>
    );
  };

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
          {devices.map(renderRow)}
        </div>
      )}
      {hiddenDevices.length > 0 && (
        <div className="dv-hidden">
          <button type="button" className="dv-link-btn" aria-expanded={showHidden} onClick={() => setShowHidden((v) => !v)}>
            <Icon name={showHidden ? "expand_less" : "expand_more"} size={14} /> {t("devices.audio.hiddenOutputs", { count: hiddenDevices.length })}
          </button>
          {showHidden && <div className="dv-list">{hiddenDevices.map(renderRow)}</div>}
        </div>
      )}
      <AudioDetailSheet device={opened} caps={caps} notify={notify} t={t} onClose={() => setOpenId(null)} onChanged={() => { void reload(); }} />
    </div>
  );
}
