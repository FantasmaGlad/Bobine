"use client";

import React from "react";
import CourseCard from "@/components/CourseCard";
import Icon from "@/components/Icon";
import type { VideoSummary } from "@/components/dashboard/LaunchSheet";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { Chapter } from "@/lib/chapters";
import type { CinemaRemoteState } from "@/lib/usePlaybackSocket";
import RemoteSeek from "./RemoteSeek";

interface CinemaNowCardProps {
  cinemaLive: CinemaRemoteState;
  videos: VideoSummary[];
  getApiUrl: (path: string) => string;
  chapters: Chapter[];
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
  onPlayPause: () => void;
}

export default function CinemaNowCard({ cinemaLive, videos, getApiUrl, chapters, sendCommand, onPlayPause }: CinemaNowCardProps) {
  const { t } = useAppSettings();
  const video = cinemaLive.video_id ? videos.find((v) => v.id === cinemaLive.video_id) ?? null : null;
  const seek = (seconds: number) => sendCommand("cinema_command", { action: "seek", position_seconds: seconds });
  return (
    <>
      <div className="now-card olc-anim-in">
        <div className="now-card__label">
          <span className="is-live" />
          {t("mobileRemote.nowPlayingCinema")}
        </div>
        <CourseCard
          variant="hero"
          getApiUrl={getApiUrl}
          releaseLabel={(release) => t("mobileRemote.releaseShort", { release })}
          fallbackProgram={t("mobileRemote.otherProgram")}
          course={{
            id: video?.id ?? cinemaLive.video_id ?? 0,
            title: cinemaLive.title ?? video?.title ?? "",
            program: video?.program ?? cinemaLive.program,
            release: video?.release,
            duration_seconds: cinemaLive.duration_seconds || video?.duration_seconds,
            thumbnail_path: video?.thumbnail_path,
          }}
        />
        <RemoteSeek position={cinemaLive.position_seconds} duration={cinemaLive.duration_seconds} chapters={chapters} onSeek={seek} />
      </div>
      <div className="mobile-remote-controls" style={{ marginTop: 0 }}>
        <button aria-label={cinemaLive.playing ? t("common.pause") : t("common.play")} className="coach-btn coach-btn-main olc-press" style={{ background: "var(--accent-primary)" }} onClick={onPlayPause}>
          <Icon name={cinemaLive.playing ? "pause" : "play_arrow"} size={38} filled />
        </button>
      </div>
      <button className="coach-btn coach-btn-wide mobile-remote-stop olc-press" onClick={() => sendCommand("cinema_command", { action: "stop" })} title={t("dashboard.cinemaStopHint")}>
        <Icon name="stop_circle" size={18} />
        {t("dashboard.stop")}
      </button>
    </>
  );
}
