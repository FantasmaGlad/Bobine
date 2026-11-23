"use client";

import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import { formatCleanDescription } from "@/lib/formatDescription";
import { formatTime } from "@/lib/format";
import { getAudioQualityBadge, getResolutionBadge } from "@/lib/videoBadges";

export interface PauseMedia {
  title: string | null;
  program?: string | null;
  release?: string | null;
  width?: number | null;
  height?: number | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
  description?: string | null;
}

interface Props {
  t: (key: string, vars?: Record<string, string | number>) => string;
  media: PauseMedia | null;
  thumbnail: string | null;
  position: number;
  duration: number;
  kicker: string;
  accent?: string;
  resumeLabel: string;
  onResume: () => void;
  back?: { label: string; onBack: () => void };
}

export function pauseMetaLine(t: Props["t"], media: PauseMedia | null, position: number, duration: number): string {
  return [
    media?.program,
    media?.release,
    getResolutionBadge(media?.width, media?.height, "HD"),
    getAudioQualityBadge(media?.audio_channels, media?.audio_codec, t("audioBadge.stereo"), t),
    duration > 0 ? `${formatTime(position)} / ${formatTime(duration)}` : null,
  ].filter(Boolean).join(" · ");
}

export default function PauseScreen({ t, media, thumbnail, position, duration, kicker, accent, resumeLabel, onResume, back }: Props) {
  return (
    <div className="pause-screen" onClick={onResume}>
      {thumbnail && <img className="pause-screen-backdrop" src={thumbnail} alt="" onError={(e) => { e.currentTarget.style.display = "none"; }} />}
      <div className="pause-screen-scrim" />
      <div className="pause-screen-content" onClick={(e) => e.stopPropagation()}>
        <AppLogo size={96} className="pause-screen-logo" />
        <p className="pause-screen-kicker" style={accent ? { color: accent } : undefined}>{kicker}</p>
        <h2 className="pause-screen-title">{media?.title}</h2>
        <p className="pause-screen-meta">{pauseMetaLine(t, media, position, duration)}</p>
        {media?.description && <p className="pause-screen-description">{formatCleanDescription(media.description)}</p>}
        <div className="pause-screen-actions">
          <button type="button" className="pause-screen-resume" onClick={onResume}>
            <Icon name="play_arrow" size={28} filled />
            {resumeLabel}
          </button>
          {back && (
            <button type="button" className="pause-screen-back" onClick={back.onBack}>
              <Icon name="arrow_back" size={22} />
              {back.label}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
