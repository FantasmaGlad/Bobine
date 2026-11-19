"use client";

import Icon from "@/components/Icon";
import { type StorageVolume } from "@/lib/storage/types";
import { type StorageCtx } from "../common";

export default function ExtensionBlock({ t, volume, busy, confirmStop, setConfirmStop, stopExtension }: {
  t: StorageCtx["t"]; volume: StorageVolume; busy: boolean; confirmStop: boolean; setConfirmStop: (value: boolean) => void; stopExtension: () => void;
}) {
  const library = volume.library;
  const videos = library?.stats?.videos ?? 0;
  const tracks = (library?.stats?.audio_tracks ?? 0) + (library?.stats?.radio_tracks ?? 0);
  const libraryCount = [videos ? t("storage.extension.videos", { count: videos }) : "", tracks ? t("storage.extension.tracks", { count: tracks }) : ""].filter(Boolean).join(" · ") || t("storage.extension.empty");
  const total = (library?.stats?.videos ?? 0) + (library?.stats?.audio_tracks ?? 0) + (library?.stats?.radio_tracks ?? 0);
  return (
      <div className="dv-detail-block">
        <div className="dv-row">
          <span className="dv-icon"><Icon name="hard_drive" size={22} /></span>
          <span className="dv-text">
            <span className="dv-title">{libraryCount}</span>
          </span>
          <span className="dv-actions">
            {confirmStop ? (
              <button type="button" className="btn btn-danger" disabled={busy} onClick={stopExtension}>{t("storage.extension.stopConfirm", { count: total })}</button>
            ) : (
              <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => (total > 0 ? setConfirmStop(true) : void stopExtension())}>{t("storage.extension.stop")}</button>
            )}
          </span>
        </div>
      </div>
  );
}
