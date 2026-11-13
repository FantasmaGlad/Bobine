"use client";
import React from "react";
import { formatTime } from "@/lib/format";
import type { PlaybackState } from "@/lib/usePlaybackSocket";

interface CoachStageProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  state: PlaybackState;
  programAccent: string;
}

export default function CoachStage({ t, state, programAccent }: CoachStageProps) {
  const currentTrack =
    state.audio_tracks && state.audio_track_index !== null && state.audio_track_index !== undefined
      ? state.audio_tracks[state.audio_track_index]
      : null;
  const audioTrackRemaining = currentTrack?.duration_seconds
    ? Math.max(0, currentTrack.duration_seconds - state.audio_position_seconds)
    : null;
  const audioTrackProgress = currentTrack?.duration_seconds
    ? Math.min(100, (state.audio_position_seconds / currentTrack.duration_seconds) * 100)
    : 0;
  return (
        <div
          className="coach-stage"
          style={{ "--coach-accent": programAccent } as React.CSSProperties}
        >
          <div className="coach-stage-glow" />
          <span className="coach-stage-eyebrow">{t("kiosk.coachModeLabel")}</span>
          <span className="coach-stage-course">{state.current_audio_course?.title}</span>
          {currentTrack ? (
            <>
              <span className="coach-stage-track-label">
                {t("kiosk.trackLabel", {
                  index: (state.audio_track_index ?? 0) + 1,
                  total: state.audio_tracks ? ` / ${state.audio_tracks.length}` : "",
                })}
              </span>
              <h1 className="coach-stage-track-title">{currentTrack.title}</h1>
              <div className="coach-stage-progress-track">
                <div className="coach-stage-progress-fill" style={{ transform: `scaleX(${audioTrackProgress / 100})` }} />
              </div>
              <div className="coach-stage-meta-row">
                <span className="coach-stage-time">{formatTime(state.audio_position_seconds)}</span>
                {!state.audio_playing && <span className="coach-stage-paused-badge">{t("kiosk.paused")}</span>}
                <span className="coach-stage-time">
                  {audioTrackRemaining !== null ? `-${formatTime(audioTrackRemaining)}` : "--:--"}
                </span>
              </div>
              {state.audio_chain_wait_remaining !== null && (
                <span className="coach-stage-next-hint">
                  {t("kiosk.nextTrackIn", { seconds: Math.ceil(state.audio_chain_wait_remaining ?? 0) })}
                </span>
              )}
            </>
          ) : (
            <span className="coach-stage-track-label">{t("kiosk.noTrack")}</span>
          )}
        </div>
  );
}
