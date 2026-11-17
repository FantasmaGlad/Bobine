"use client";

import React from "react";
import CourseCard from "@/components/CourseCard";
import SubtitlePicker from "@/components/SubtitlePicker";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { Chapter } from "@/lib/chapters";
import type { PlaybackState } from "@/lib/usePlaybackSocket";
import RemoteSeek from "./RemoteSeek";

interface KioskNowCardProps {
  state: PlaybackState;
  livePosition: number;
  getApiUrl: (path: string) => string;
  chapters: Chapter[];
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
}

export default function KioskNowCard({ state, livePosition, getApiUrl, chapters, sendCommand }: KioskNowCardProps) {
  const { t } = useAppSettings();
  const duration = state.current_video?.duration_seconds ?? 0;
  const nextPlaylistItem =
    state.playlist_items && state.playlist_index !== null && state.playlist_index !== undefined
      ? state.playlist_items[state.playlist_index + 1]
      : null;
  return (
    <div className="now-card olc-anim-in">
      <div className="now-card__label">
        <span className="is-live" />
        {state.playlist_name ? state.playlist_name : t("mobileRemote.nowPlaying")}
      </div>
      {state.current_video ? (
        <CourseCard
          variant="hero"
          getApiUrl={getApiUrl}
          releaseLabel={(release) => t("mobileRemote.releaseShort", { release })}
          fallbackProgram={t("mobileRemote.otherProgram")}
          course={state.current_video}
        />
      ) : (
        <div className="mobile-remote-now">
          <span className="mobile-remote-title">{state.current_background?.title ?? ""}</span>
        </div>
      )}
      <RemoteSeek
        position={livePosition}
        duration={duration}
        chapters={chapters}
        disabled={state.state === "background"}
        onSeek={(seconds) => sendCommand("seek", { position_seconds: seconds })}
      />
      {state.current_video && (
        <SubtitlePicker videoId={state.current_video.id} subtitle={state.subtitle} getApiUrl={getApiUrl} onChange={(subtitle) => sendCommand("set_subtitle", { subtitle })} />
      )}
      {nextPlaylistItem && state.state !== "playlist_waiting" && (
        <div className="now-card__next">
          {t("kiosk.nextCourseLabel")} {nextPlaylistItem.title}
        </div>
      )}
    </div>
  );
}
