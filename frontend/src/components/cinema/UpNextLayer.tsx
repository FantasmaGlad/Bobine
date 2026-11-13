"use client";

import React from "react";

import CourseRatingWidget from "@/components/CourseRatingWidget";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { thumbnailUrl, type CinemaVideo } from "@/lib/cinemaCatalog";
import { formatMinutes, formatTime } from "@/lib/format";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";

export const UP_NEXT_AUTOPLAY_SECONDS = 5 * 60;

interface Props {
  visible: boolean;
  ended: CinemaVideo | null;
  upNext: CinemaVideo | null;
  remaining: number;
  onPlay: (video: CinemaVideo) => void;
  onBack: () => void;
  onCloseRating: () => void;
}

function UpNextCard({ upNext, remaining, onPlay, onBack }: { upNext: CinemaVideo; remaining: number; onPlay: () => void; onBack: () => void }) {
  const { t } = useAppSettings();
  const themeFg = useThemeAccentForeground();
  const thumb = thumbnailUrl(upNext);
  const progress = (1 - remaining / UP_NEXT_AUTOPLAY_SECONDS) * 360;
  return (
    <div className="cinema-upnext-card" style={{ "--upnext-accent": "var(--accent-primary)" } as React.CSSProperties}>
      <span className="cinema-upnext-label">{t("cinema.upNext")}</span>
      <button className="cinema-upnext-thumb" onClick={onPlay} title={t("cinema.playNow")}>
        {thumb ? (
          <img src={thumb} alt="" />
        ) : (
          <Icon name="movie" size={48} color="var(--text-dim)" />
        )}
        <span className="cinema-upnext-ring" style={{ background: `conic-gradient(var(--upnext-accent) ${progress}deg, color-mix(in srgb, var(--specular) 18%, transparent) 0deg)` }}>
          <span className="cinema-upnext-ring-inner"><Icon name="play_arrow" size={34} filled /></span>
        </span>
      </button>
      <h2 className="cinema-upnext-title">{upNext.title}</h2>
      <p className="cinema-upnext-meta">{[upNext.program, upNext.release, formatMinutes(upNext.duration_seconds)].filter(Boolean).join(" · ")}</p>
      <p className="cinema-upnext-autoplay">{t("cinema.autoPlayIn", { time: formatTime(remaining) })}</p>
      <div className="cinema-upnext-actions">
        <button className="cinema-hero-play" style={{ color: themeFg }} onClick={onPlay}>
          <Icon name="play_arrow" size={22} color={themeFg} filled />
          {t("cinema.playNow")}
        </button>
        <button className="cinema-ctl-btn" onClick={onBack}>
          <Icon name="arrow_back" size={20} color="currentColor" />
          {t("cinema.backToMenu")}
        </button>
      </div>
    </div>
  );
}

export default function UpNextLayer({ visible, ended, upNext, remaining, onPlay, onBack, onCloseRating }: Props) {
  const { wiredDisplayMode, waitTimeBetweenCourses } = useAppSettings();
  return (
    <div className={`cinema-layer cinema-upnext ${visible ? "visible" : ""}`} style={!visible ? { display: "none", pointerEvents: "none" } : undefined}>
      <div className="cinema-upnext-layout">
        {ended && wiredDisplayMode === "headless" && (
          <div className="cinema-rating-container">
            <CourseRatingWidget videoId={ended.id} courseTitle={ended.title} channel="cable" isCinemaMode={true}
              autoCloseSeconds={waitTimeBetweenCourses > 0 ? waitTimeBetweenCourses : 20} onClose={onCloseRating} />
          </div>
        )}
        {upNext && <UpNextCard upNext={upNext} remaining={remaining} onPlay={() => onPlay(upNext)} onBack={onBack} />}
      </div>
    </div>
  );
}
