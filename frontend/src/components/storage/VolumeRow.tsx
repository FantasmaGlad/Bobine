"use client";

import Icon from "@/components/Icon";
import {
  formatBytes, healthWarningKeys, portableIcon, primaryAction, statusIcon, volumeIcon, volumeStatus,
  type PortableDevice, type StorageVolume,
} from "@/lib/storageApi";
import { tr, type StorageCtx } from "./common";

interface VolumeProps extends StorageCtx {
  volume: StorageVolume;
  busy: boolean;
  onExplore: () => void;
  onMore: () => void;
}

/** Un support : nom, état en un mot, place libre, UNE action principale (Explorer) et le menu d'options. */
export function VolumeRow({ volume, busy, onExplore, onMore, t, lang }: VolumeProps) {
  const status = volumeStatus(volume);
  const action = primaryAction(volume);
  const offline = status === "offline";
  const stats = volume.library?.stats;
  const itemCount = (stats?.videos ?? 0) + (stats?.audio_tracks ?? 0) + (stats?.radio_tracks ?? 0);
  const warning = healthWarningKeys(volume.health)[0];
  const sub = offline
    ? itemCount > 0 ? t("storage.offlineInfo", { count: itemCount }) : t("storage.offlineEmpty")
    : volume.usage
      ? t("storage.free", { free: formatBytes(volume.usage.free_bytes, lang), size: formatBytes(volume.usage.total_bytes, lang) })
      : formatBytes(volume.size_bytes, lang);
  return (
    <div className={`dv-row glass-interactive${offline ? " off" : ""}`} data-focus-id={volume.key}>
      <span className="dv-icon"><Icon name={volumeIcon(volume.kind)} size={24} /></span>
      <span className="dv-text">
        <span className="dv-title">{volume.name}</span>
        <span className="dv-sub">
          <Icon name={statusIcon(status)} size={14} className={status === "busy" ? "olc-spin" : ""} /> {t(`storage.status.${status}`)}
          {" · "}{t(`storage.kinds.${volume.kind}`)} · {sub}
        </span>
        {status === "attention" && warning && <span className="dv-sub">{tr(t, `storage.warnings.${warning}`, warning)}</span>}
      </span>
      <span className="dv-actions">
        {action === "explore" && (
          <button type="button" className="btn btn-primary" disabled={busy} onClick={onExplore}>
            <Icon name={busy ? "sync" : "folder_open"} size={18} className={busy ? "olc-spin" : ""} /> {busy ? t("storage.opening") : t("storage.explore")}
          </button>
        )}
        <button type="button" className="btn btn-secondary st-more" onClick={onMore} aria-label={t("storage.more")} title={t("storage.more")}><Icon name="more_horiz" size={18} /></button>
      </span>
    </div>
  );
}

interface PortableProps extends StorageCtx {
  device: PortableDevice;
  busy: boolean;
  onOpen: () => void;
}

/** Téléphone ou tablette : lecture seule, import uniquement ; l'état dit quoi faire sur l'appareil. */
export function PortableRow({ device, busy, onOpen, t }: PortableProps) {
  const ready = device.state === "ready" || device.state === "mounted";
  const hintKey = device.state === "busy" ? "busy" : device.state === "detected" || device.state === "not_ready" || device.state === "locked" || device.state === "needs_approval" ? "waiting" : "";
  const hint = hintKey ? t(`storage.portable.hints.${hintKey}`) : "";
  return (
    <div className={`dv-row glass-interactive${ready ? "" : " off"}`} data-focus-id={device.id}>
      <span className="dv-icon"><Icon name={portableIcon(device.scheme)} size={24} /></span>
      <span className="dv-text">
        <span className="dv-title">{device.name}</span>
        <span className="dv-sub">
          <Icon name={ready ? "check_circle" : "info"} size={14} /> {tr(t, `storage.portable.states.${device.state}`, device.state)} · {t("storage.portable.readOnly")}
        </span>
        {hint && <span className="dv-sub">{hint}</span>}
        {device.state === "missing_tool" && device.install && <span className="dv-sub">{t("storage.portable.install")} <code>{device.install}</code></span>}
      </span>
      {ready && (
        <span className="dv-actions">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={onOpen}>
            <Icon name={busy ? "sync" : "folder_open"} size={18} className={busy ? "olc-spin" : ""} /> {busy ? t("storage.opening") : t("storage.explore")}
          </button>
        </span>
      )}
    </div>
  );
}
