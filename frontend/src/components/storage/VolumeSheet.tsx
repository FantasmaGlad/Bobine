"use client";

import Icon from "@/components/Icon";
import Sheet from "@/components/Sheet";
import FsVerdictBlock from "./sheet/FsVerdictBlock";
import ExtensionBlock from "./sheet/ExtensionBlock";
import HealthBlock from "./sheet/HealthBlock";
import ProtectionFold from "./sheet/ProtectionFold";
import { useVolumeActions } from "./sheet/useVolumeActions";
import { type StorageVolume } from "@/lib/storage/types";
import { type StorageCtx } from "./common";

interface Props extends StorageCtx {
  volume: StorageVolume | null;
  onClose: () => void;
  onChanged: () => void;
  onAdvice: () => void;
  onPrepare: () => void;
}
export default function VolumeSheet({ volume, onClose, onChanged, onAdvice, onPrepare, t, lang, notify }: Props) {
  const actions = useVolumeActions(volume, { t, lang, notify }, onChanged, onClose);
  const { busy, health, confirmStop, setConfirmStop, setSetting, eject, stopExtension, refreshHealth } = actions;
  if (!volume) return <Sheet open={false} onClose={onClose}>{null}</Sheet>;
  const registered = !!volume.library?.registered;
  const shownHealth = health ?? volume.health;

  return (
    <Sheet
      open
      onClose={onClose}
      title={volume.name}
      closeLabel={t("storage.close")}
      footer={
        volume.connected ? (
          <div className="dv-actions">
            <button type="button" className="btn btn-primary" disabled={busy || volume.state === "busy"} onClick={eject}><Icon name="eject" size={18} /> {t("storage.eject")}</button>
          </div>
        ) : undefined
      }
    >
      <div className="dv-detail">
        <FsVerdictBlock t={t} volume={volume} onAdvice={onAdvice} />
        {volume.connected && <HealthBlock t={t} lang={lang} volume={volume} shownHealth={shownHealth} busy={busy} refreshHealth={refreshHealth} />}
        {volume.connected && <ProtectionFold t={t} volume={volume} disabled={busy || !registered} setSetting={setSetting} />}
        {volume.connected && volume.state !== "formatting" && (
          <div className="dv-detail-block">
            <div className="dv-row">
              <span className="dv-icon"><Icon name="cleaning_services" size={22} /></span>
              <span className="dv-text">
                <span className="dv-title">{t("storage.format.entryTitle")}</span>
                <span className="dv-sub">{t("storage.format.entryHint")}</span>
              </span>
              <span className="dv-actions"><button type="button" className="btn btn-danger" disabled={busy || volume.state === "busy"} onClick={onPrepare}>{t("storage.format.entryTitle")}</button></span>
            </div>
          </div>
        )}
        {registered && (
          <ExtensionBlock t={t} volume={volume} busy={busy} confirmStop={confirmStop} setConfirmStop={setConfirmStop} stopExtension={stopExtension} />
        )}
      </div>
    </Sheet>
  );
}
