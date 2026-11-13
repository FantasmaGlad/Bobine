"use client";

import { useState } from "react";

import ChapterList from "@/components/ChapterList";
import ChapterTicks from "@/components/ChapterTicks";
import type { NowPlaying } from "@/components/cinema/useNowPlaying";
import type { CinemaRemoteState } from "@/lib/usePlaybackSocket";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { useVideoChapters } from "@/lib/chapters";
import { formatTime } from "@/lib/format";

import { THUMB_STYLE, type Send, type VideoSummary } from "./types";

interface Props {
  remote: NowPlaying<CinemaRemoteState>;
  video: VideoSummary | null;
  thumb: string | null;
  sendCommand: Send;
}

export default function LiveCinema({ remote, video, thumb, sendCommand }: Props) {
  const { t } = useAppSettings();
  const [drag, setDrag] = useState<number | null>(null);
  const live = remote.nowPlaying;
  const chapters = useVideoChapters(live?.video_id, getApiUrl);
  if (!live) return <div className="live-empty">{t("dashboard.cinemaNoPlayback")}</div>;
  const seek = (seconds: number) => sendCommand("cinema_command", { action: "seek", position_seconds: seconds });
  const release = (e: { target: EventTarget }) => {
    seek(Number((e.target as HTMLInputElement).value));
    setDrag(null);
  };
  const program = video?.program ?? live.program;
  const meta = [program, video?.release ? `#${video.release}` : null].filter(Boolean).join(" · ");
  const shown = drag ?? live.position_seconds;
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        {thumb ? <img src={thumb} alt="" style={THUMB_STYLE} /> : null}
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <div className="live-title">{live.title}</div>
          {meta && <span style={{ fontSize: "0.8rem", color: "var(--accent-text)", fontWeight: 700 }}>{meta}</span>}
        </div>
      </div>
      <div className="live-progress">
        <span className="live-time">{formatTime(shown)}</span>
        <div className="chapter-seek">
          <input type="range" min={0} max={live.duration_seconds || 0} step={1} value={shown} onChange={(e) => setDrag(Number(e.target.value))} onMouseUp={release} onTouchEnd={release} className="seek-slider" />
          <ChapterTicks chapters={chapters} duration={live.duration_seconds || 0} />
        </div>
        <span className="live-time">{formatTime(live.duration_seconds)}</span>
      </div>
      <ChapterList chapters={chapters} position={shown} onSeek={seek} className="chapter-list--inline" />
      <div className="live-controls">
        <button className="btn btn-secondary control-btn" onClick={() => sendCommand("cinema_command", { action: "stop" })} title={t("dashboard.cinemaStopHint")}>
          <Icon name="stop" size={18} />
          {t("dashboard.stop")}
        </button>
        <button className="btn btn-primary control-btn control-btn-main" onClick={remote.playPause}>
          <Icon name={live.playing ? "pause" : "play_arrow"} size={20} filled />
          {live.playing ? t("dashboard.pause") : t("dashboard.play")}
        </button>
      </div>
    </>
  );
}
