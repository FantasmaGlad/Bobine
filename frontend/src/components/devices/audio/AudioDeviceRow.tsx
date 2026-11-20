"use client";

import Icon from "@/components/Icon";
import { audioDisplayName, audioKindIcon } from "@/lib/devices/audio";
import { type AudioDevice } from "@/lib/devices/types";
import { type SectionProps } from "../shared/section";
import { type AudioCalls } from "./useAudioCalls";

interface RowProps {
  device: AudioDevice;
  selected: boolean;
  canVolume: boolean;
  canDefault: boolean;
  calls: AudioCalls;
  onOpen: (id: string) => void;
  t: SectionProps["t"];
}

const stop = (e: React.SyntheticEvent) => e.stopPropagation();

function DeviceText({ device, t }: { device: AudioDevice; t: SectionProps["t"] }) {
  return (
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
  );
}

function VolumeControl({ device, calls, t }: RowProps) {
  const { draft, setDraft, call, commitVolume } = calls;
  const volume = draft[device.id] ?? Math.round((device.volume ?? 0) * 100);
  return (
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
  );
}

export default function AudioDeviceRow(props: RowProps) {
  const { device, selected, canVolume, canDefault, calls, onOpen, t } = props;
  const open = () => onOpen(device.id);
  return (
    <div
      role="button"
      tabIndex={0}
      data-focus-id={device.id}
      aria-label={t("devices.audio.openDetail", { name: audioDisplayName(device) })}
      className={`dv-row glass-interactive dv-row--click ${device.is_default ? "active" : ""} ${selected ? "is-selected" : ""} ${device.available ? "" : "off"}`}
      onClick={open}
      onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); open(); } }}
    >
      <span className="dv-icon"><Icon name={audioKindIcon(device.kind)} size={22} /></span>
      <DeviceText device={device} t={t} />
      {canVolume && device.volume !== null && <VolumeControl {...props} />}
      {canDefault && !device.is_default && (
        <button type="button" className="btn btn-secondary" onClick={(e) => { stop(e); void calls.call("/audio/default", { id: device.id }, t("devices.audio.defaultSet")); }}>
          {t("devices.audio.use")}
        </button>
      )}
      <span className="dv-chevron" aria-hidden="true"><Icon name="chevron_right" size={20} /></span>
    </div>
  );
}
