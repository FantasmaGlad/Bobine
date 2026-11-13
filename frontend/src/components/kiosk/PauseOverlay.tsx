"use client";
import React from "react";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import { formatCleanDescription } from "@/lib/formatDescription";
import { formatTime } from "@/lib/format";
import type { PlaybackState } from "@/lib/usePlaybackSocket";
import { getAudioQualityBadge, getResolutionBadge } from "@/lib/videoBadges";
import { getThumbnailSrc } from "./media";

interface PauseOverlayProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  state: PlaybackState;
  programAccent: string;
  onResume: () => void;
}

export default function PauseOverlay({ t, state, programAccent, onResume }: PauseOverlayProps) {
  const program = state.current_video?.program ?? state.current_audio_course?.program ?? undefined;
  const duration = state.current_video?.duration_seconds ?? 0;
  const pauseProgressPercent = duration > 0 ? Math.min(100, (state.position_seconds / duration) * 100) : 0;
  return (
        <div className="pause-overlay visible" onClick={() => onResume()}>
          <div className="pause-center" onClick={(e) => { e.stopPropagation(); }}>
            <div className="pause-media-col">
              <div
                className="pause-thumb-wrap"
                onClick={() => onResume()}
                title={t("kiosk.resume")}
              >
                {(() => {
                  const thumbSrc = getThumbnailSrc(state.current_video?.thumbnail_url || state.current_video?.thumbnail_path);
                  return thumbSrc ? (
                    <img
                      src={thumbSrc}
                      alt={state.current_video?.title || ""}
                      className="pause-thumb-img"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  ) : (
                    <div className="pause-thumb-fallback">
                      <AppLogo size={90} className="pause-logo" />
                    </div>
                  );
                })()}
                <div className="pause-thumb-overlay-btn">
                  <Icon name="play_arrow" size={48} filled />
                </div>
                <div className="pause-thumb-time">
                  {formatTime(state.position_seconds)} / {formatTime(duration)}
                </div>
              </div>

              <div className="pause-logo-mini-wrap">
                <AppLogo size={80} className="pause-logo" />
              </div>
            </div>

            <div className="pause-details-col">
              <div>
                <div className="pause-header-row">
                  <span className="pause-kicker" style={{ color: programAccent }}>
                    {t("kiosk.pausedLabel")}
                  </span>
                  {program && (
                    <span className="pause-badge" style={{ color: programAccent }}>
                      {program}
                    </span>
                  )}
                  {state.current_video?.release && (
                    <span className="pause-year">{state.current_video.release}</span>
                  )}
                  {getResolutionBadge(state.current_video?.width, state.current_video?.height, "HD") && (
                    <span className="pause-badge-pill">
                      {getResolutionBadge(state.current_video?.width, state.current_video?.height, "HD")}
                    </span>
                  )}
                  {getAudioQualityBadge(state.current_video?.audio_channels, state.current_video?.audio_codec, t("audioBadge.stereo"), t) && (
                    <span className="pause-badge-pill">
                      {getAudioQualityBadge(state.current_video?.audio_channels, state.current_video?.audio_codec, t("audioBadge.stereo"), t)}
                    </span>
                  )}
                </div>

                <h2 className="pause-title">{state.current_video?.title}</h2>
              </div>

              {state.current_video?.description ? (
                <div className="pause-description-scroll">
                  <p className="pause-description-text">{formatCleanDescription(state.current_video.description)}</p>
                </div>
              ) : (
                <div style={{ flex: 1 }} />
              )}

              <div className="pause-actions-row">
                <button
                  className="pause-resume-btn-pill"
                  onClick={() => onResume()}
                  title={t("kiosk.resume")}
                >
                  <Icon name="play_arrow" size={24} filled />
                  <span>{t("kiosk.resume")}</span>
                </button>
              </div>
            </div>
          </div>
          <div className="pause-progress-track">
            <div className="pause-progress-fill" style={{ transform: `scaleX(${pauseProgressPercent / 100})` }} />
          </div>
        </div>
  );
}
