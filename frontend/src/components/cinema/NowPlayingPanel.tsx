"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatTime } from "@/lib/format";

import type { NowPlaying } from "./useNowPlaying";

export default function NowPlayingPanel({ remote }: { remote: NowPlaying }) {
  const { t } = useAppSettings();
  const [drag, setDrag] = useState<number | null>(null);
  const now = remote.nowPlaying!;
  const shown = drag ?? now.position_seconds;
  const button = (icon: string, label: string, onClick: () => void, main = false) => (
    <button type="button" className={`grid-now-playing-btn${main ? " grid-now-playing-btn-main" : ""}`} onClick={onClick} title={label} aria-label={label}>
      <Icon name={icon} size={main ? 30 : 24} filled={main} />
    </button>
  );
  return (
    <section className="grid-now-playing">
      <button type="button" className="grid-now-playing-close" onClick={remote.stop} aria-label={t("common.stop")} title={t("common.stop")}>
        <Icon name="close" size={18} />
      </button>
      <span className="grid-now-playing-label">{t("cinema.nowPlaying")}</span>
      <h2 className="grid-now-playing-title">{now.title}</h2>
      <input
        type="range"
        className="grid-now-playing-seek"
        min={0}
        max={now.duration_seconds || 0}
        step={1}
        value={shown}
        onChange={(e) => setDrag(Number(e.target.value))}
        onPointerUp={(e) => {
          const target = Number((e.target as HTMLInputElement).value);
          setDrag(null);
          remote.seekDelta(target - now.position_seconds);
        }}
        aria-label={t("cinema.seekPosition")}
      />
      <div className="grid-now-playing-times">
        <span>{formatTime(shown)}</span>
        <span>{formatTime(now.duration_seconds)}</span>
      </div>
      <div className="grid-now-playing-controls">
        {button("replay_30", t("cinema.back30"), () => remote.seekDelta(-30))}
        {button(now.playing ? "pause" : "play_arrow", now.playing ? t("cinema.pause") : t("cinema.play"), remote.playPause, true)}
        {button("forward_30", t("cinema.forward30"), () => remote.seekDelta(30))}
      </div>
    </section>
  );
}
