"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";

interface VolumeOsdProps {
  visible: boolean;
  level: number;
  muted?: boolean;
  overVideo?: boolean;
}

export default function VolumeOsd({ visible, level, muted = false, overVideo = false }: VolumeOsdProps) {
  const { t } = useAppSettings();
  const percent = muted ? 0 : Math.round(Math.max(0, Math.min(1, level)) * 100);

  return (
    <div
      className={`volume-osd ${visible ? "is-visible" : ""} ${overVideo ? "is-flat" : ""}`}
      role="status"
      aria-live="polite"
      aria-label={muted ? t("common.volumeMuted") : t("common.volumeLevel", { percent })}
    >
      <div className="volume-osd-track">
        <div className="volume-osd-fill" style={{ transform: `scaleY(${percent / 100})` }} />
      </div>
      <span className="volume-osd-value">{percent}</span>
    </div>
  );
}
