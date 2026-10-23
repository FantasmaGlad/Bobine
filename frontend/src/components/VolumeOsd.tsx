"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";

interface VolumeOsdProps {
  visible: boolean;
  /** 0 à 1. */
  level: number;
  muted?: boolean;
  /** Posé sur une vidéo en lecture : pas de flou (trop coûteux à chaque image sur le matériel visé). */
  overVideo?: boolean;
}

/** Indicateur de volume latéral (clavier, manette, télécommande à dongle) : verre aux jetons du thème, jauge et valeur (la sourdine se lit 0). */
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
        <div className="volume-osd-fill" style={{ height: `${percent}%` }} />
      </div>
      <span className="volume-osd-value">{percent}</span>
    </div>
  );
}
