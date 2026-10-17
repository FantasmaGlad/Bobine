"use client";

import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useVideoSubtitles } from "@/lib/subtitles";

interface SubtitlePickerProps {
  videoId: number | null | undefined;
  /** Choix diffusé par le serveur : null = piste par défaut, "off" = aucune, sinon identifiant. */
  subtitle: number | "off" | null | undefined;
  getApiUrl: (path: string) => string;
  onChange: (subtitle: number | "off") => void;
  className?: string;
}

/** Sélecteur de sous-titres du cours en cours (absent si le cours n'en a pas). */
export default function SubtitlePicker({ videoId, subtitle, getApiUrl, onChange, className = "" }: SubtitlePickerProps) {
  const { t } = useAppSettings();
  const tracks = useVideoSubtitles(videoId, getApiUrl);
  if (tracks.length === 0) return null;

  const current = subtitle === "off" ? "off" : String(subtitle ?? tracks[0].id);

  return (
    <div className={`subtitle-picker ${className}`.trim()}>
      <span className="subtitle-picker__label">
        <Icon name="subtitles" size={18} />
        {t("dashboard.subtitlesLabel")}
      </span>
      <ResponsiveSelect
        value={current}
        onChange={(value) => onChange(value === "off" ? "off" : Number(value))}
        title={t("dashboard.subtitlesLabel")}
        searchable={false}
        options={[
          { value: "off", label: t("dashboard.subtitlesOff") },
          ...tracks.map((track) => ({ value: String(track.id), label: track.language_label })),
        ]}
      />
    </div>
  );
}
