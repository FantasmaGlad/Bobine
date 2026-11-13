"use client";
import React from "react";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import { formatTime, formatWallClock } from "@/lib/format";
import type { RadioState } from "@/lib/useRadioSocket";

interface NowPlayingProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  state: RadioState;
  connected: boolean;
  now: Date | null;
  livePosition: number;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
  handlePlayPause: () => void;
}

export default function NowPlaying({ t, state, connected, now, livePosition, sendCommand, handlePlayPause }: NowPlayingProps) {
  const currentTrack = state.current_track;
  const coverSrc = currentTrack?.cover_url ? getApiUrl(currentTrack.cover_url) : null;
  const duration = state.duration_seconds ?? currentTrack?.duration_seconds ?? 0;
  return (
    <>
      {!currentTrack ? (
        <>
          <AppLogo className="radio-brand-logo" />
          <span className="radio-screen-clock">{formatWallClock(now)}</span>
          <span className="radio-screen-idle-label">
            {connected ? t("radioScreen.idleHint") : t("radioRemote.disconnected")}
          </span>
        </>
      ) : (
        <>
          <div className="radio-cover">
            {coverSrc ? <img src={coverSrc} alt="" /> : <Icon name="music_note" size={64} />}
          </div>

          <div>
            <div className="radio-meta-title">{currentTrack.title}</div>
            <div className="radio-meta-artist">
              {currentTrack.artist || t("radioLibrary.unknownArtist")}
              {currentTrack.album ? ` — ${currentTrack.album}` : ""}
            </div>
          </div>

          <div className="radio-screen-progress">
            <span>{formatTime(livePosition)}</span>
            <input
              type="range"
              min={0}
              max={duration || 0}
              step={1}
              value={livePosition}
              onChange={(e) => sendCommand("radio_seek", { position_seconds: Number(e.target.value) })}
              className="seek-slider"
              style={{ flex: 1 }}
            />
            <span>{formatTime(duration)}</span>
          </div>

          <div className="radio-screen-controls">
            <button className="radio-transport-btn" onClick={() => sendCommand("radio_previous_track")} title={t("radioRemote.previousTrack")}>
              <Icon name="skip_previous" size={22} filled />
            </button>
            <button className="radio-transport-btn main" onClick={handlePlayPause}>
              <Icon name={state.playing ? "pause" : "play_arrow"} size={30} filled />
            </button>
            <button className="radio-transport-btn" onClick={() => sendCommand("radio_next_track")} title={t("radioRemote.nextTrack")}>
              <Icon name="skip_next" size={22} filled />
            </button>
          </div>

          <div className="radio-screen-volume">
            <Icon name="volume_up" size={18} />
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={state.volume}
              onChange={(e) => sendCommand("volume", { volume: Number(e.target.value) })}
              className="volume-slider"
              style={{ flex: 1 }}
            />
            <span>{state.volume}%</span>
          </div>
        </>
      )}
    </>
  );
}
