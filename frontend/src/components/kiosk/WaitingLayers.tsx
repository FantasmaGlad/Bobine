"use client";
import React from "react";
import AppLogo from "@/components/AppLogo";
import { formatWallClock } from "@/lib/format";
import type { PlaybackState } from "@/lib/usePlaybackSocket";
import { formatDuration, type NextCourse } from "./media";

interface WaitingLayersProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  state: PlaybackState;
  now: Date;
  nextCourse: NextCourse | null;
}

export default function WaitingLayers({ t, state, now, nextCourse }: WaitingLayersProps) {
  const isIdle = state.state === "waiting" || state.state === "offline";
  const nextCourseRemaining = nextCourse ? Math.max(0, (new Date(nextCourse.run_at).getTime() - now.getTime()) / 1000) : null;
  const nextPlaylistItem = state.playlist_items && state.playlist_index !== null && state.playlist_index !== undefined
    ? state.playlist_items[state.playlist_index + 1]
    : null;
  return (
    <>
      <div className={`kiosk-layer kiosk-waiting ${isIdle ? "visible" : ""}`}>
        <div className="kiosk-waiting-content">
          <span className="kiosk-waiting-clock" suppressHydrationWarning>{formatWallClock(now)}</span>
          <div className="kiosk-waiting-logo-wrap">
            <AppLogo className="kiosk-waiting-stage-logo" />
          </div>
          <div className="kiosk-waiting-next">
            {nextCourse ? (
              <>
                <span className="kiosk-waiting-next-label">
                  {t("kiosk.nextCourseLabel")}
                </span>
                <span className="kiosk-waiting-next-title">
                  {nextCourse.title ?? t("kiosk.scheduledCourseFallback")}
                </span>
                <span className="kiosk-waiting-next-countdown">
                  {formatDuration(nextCourseRemaining ?? 0)}
                </span>
              </>
            ) : (
              <span className="kiosk-waiting-next-empty">
                {t("kiosk.waitingForNextCourse")}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className={`kiosk-layer kiosk-playlist-waiting ${state.state === "playlist_waiting" ? "visible" : ""}`}>
        <AppLogo size={110} className="kiosk-waiting-logo" />
        <span className="kiosk-clock" suppressHydrationWarning>{formatWallClock(now)}</span>
        <div className="kiosk-playlist-info">
          <span className="kiosk-playlist-label">{t("kiosk.activePlaylist")}</span>
          <span className="kiosk-playlist-name">{state.playlist_name}</span>
        </div>
        {nextPlaylistItem ? (
          <div className="kiosk-next-course">
            <span className="kiosk-next-course-label">{t("kiosk.nextCourseLabel")}</span>
            <span className="kiosk-next-course-title">{nextPlaylistItem.title}</span>
            <span className="kiosk-playlist-countdown-number" style={{ color: "var(--accent-text)" }}>
              {Math.ceil(state.playlist_waiting_remaining ?? 0)}
            </span>
          </div>
        ) : (
          <span className="kiosk-waiting-sub">{t("kiosk.playlistEnd")}</span>
        )}
      </div>
    </>
  );
}
