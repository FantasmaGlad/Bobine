"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import MarqueeText from "@/components/MarqueeText";
import { formatTime } from "@/lib/format";

interface NowPlayingCardProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  nowPlaying: { title?: string | null; video_id?: number | null; position_seconds: number; duration_seconds: number; playing: boolean };
  handleNowPlayingStop: () => void;
  handleNowPlayingPlayPause: () => void;
  handleNowPlayingSeekDelta: (delta: number) => void;
  commitSeek: (position: number) => void;
}

export default function NowPlayingCard({
  t, nowPlaying, handleNowPlayingStop, handleNowPlayingPlayPause, handleNowPlayingSeekDelta, commitSeek,
}: NowPlayingCardProps) {
  const [nowPlayingSeekDrag, setNowPlayingSeekDrag] = useState<number | null>(null);
  const commit = (value: number) => {
    commitSeek(value);
    setNowPlayingSeekDrag(null);
  };
  return (
        <section className="grid-now-playing">
          <button
            className="grid-now-playing-close"
            onClick={handleNowPlayingStop}
            title={t("cinema.removeCourse")}
            aria-label={t("cinema.removeCourse")}
          >
            <Icon name="close" size={18} />
          </button>
          <span className="grid-now-playing-label">{t("cinema.nowPlaying")}</span>
          <MarqueeText text={nowPlaying.title} className="grid-now-playing-title" />
          <input
            type="range"
            className="grid-now-playing-seek"
            min={0}
            max={nowPlaying.duration_seconds || 0}
            step={1}
            value={nowPlayingSeekDrag ?? nowPlaying.position_seconds}
            onChange={(e) => setNowPlayingSeekDrag(Number(e.target.value))}
            onMouseUp={(e) => commit(Number((e.target as HTMLInputElement).value))}
            onTouchEnd={(e) => commit(Number((e.target as HTMLInputElement).value))}
          />
          <div className="grid-now-playing-times">
            <span>{formatTime(nowPlayingSeekDrag ?? nowPlaying.position_seconds)}</span>
            <span>{formatTime(nowPlaying.duration_seconds)}</span>
          </div>
          <div className="grid-now-playing-controls">
            <button
              className="grid-now-playing-btn"
              onClick={() => handleNowPlayingSeekDelta(-10)}
              title={t("cinema.seekBack")}
              aria-label={t("cinema.seekBack")}
            >
              <Icon name="replay_10" size={26} />
            </button>
            <button
              className="grid-now-playing-btn grid-now-playing-btn-main"
              onClick={handleNowPlayingPlayPause}
              title={nowPlaying.playing ? t("cinema.pause") : t("cinema.play")}
            >
              <Icon name={nowPlaying.playing ? "pause" : "play_arrow"} size={30} filled />
            </button>
            <button
              className="grid-now-playing-btn"
              onClick={() => handleNowPlayingSeekDelta(10)}
              title={t("cinema.seekForward")}
              aria-label={t("cinema.seekForward")}
            >
              <Icon name="forward_10" size={26} />
            </button>
          </div>
        </section>
  );
}
