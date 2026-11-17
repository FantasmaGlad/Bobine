"use client";

import React from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { RadioState } from "@/lib/useRadioSocket";
import SeekBar from "./SeekBar";
import TrackSummary from "./TrackSummary";
import TransportControls from "./TransportControls";
import type { SendRadioCommand } from "./types";
import VolumeControl from "./VolumeControl";

interface NowPlayingCardProps {
  state: RadioState;
  connected: boolean;
  livePosition: number;
  sendCommand: SendRadioCommand;
}

const PLAYLIST_BADGE: React.CSSProperties = {
  fontSize: "0.85rem",
  color: "var(--accent-text)",
  fontWeight: 700,
  background: "color-mix(in srgb, var(--accent-primary) 6%, transparent)",
  padding: "8px 14px",
  borderRadius: "var(--radius-md)",
  border: "1px solid color-mix(in srgb, var(--accent-primary) 20%, transparent)",
  width: "fit-content",
};

export default function NowPlayingCard({ state, connected, livePosition, sendCommand }: NowPlayingCardProps) {
  const { t } = useAppSettings();
  const currentTrack = state.current_track;
  const coverSrc = currentTrack?.cover_url ? getApiUrl(currentTrack.cover_url) : null;
  const duration = state.duration_seconds ?? currentTrack?.duration_seconds ?? 0;
  return (
    <div className="live-block bento-hero-live" style={{ position: "relative", overflow: "hidden" }}>
      {coverSrc && <div className="bento-hero-backdrop" style={{ backgroundImage: `url(${coverSrc})`, opacity: 0.25 }} />}
      <div className="bento-hero-content">
        <div className="live-header">
          <h3>
            <Icon name="graphic_eq" size={18} />
            {t("radioRemote.title")}
          </h3>
          <span className={`status-pill ${connected ? "ok" : "down"}`}>
            {!connected ? t("radioRemote.disconnected") : t(`radioRemote.stateLabels.${state.state}`)}
          </span>
        </div>
        {state.playlist_name && (
          <div style={PLAYLIST_BADGE}>
            {t("radioRemote.playlistLabel", { name: state.playlist_name, index: (state.index ?? 0) + 1, total: state.order.length })}
          </div>
        )}
        {currentTrack ? (
          <>
            <TrackSummary track={currentTrack} coverSrc={coverSrc} />
            <SeekBar position={livePosition} duration={duration} sendCommand={sendCommand} />
            <TransportControls playing={state.playing} shuffle={state.shuffle} repeat={state.repeat} sendCommand={sendCommand} />
            <VolumeControl volume={state.volume} sendCommand={sendCommand} />
          </>
        ) : (
          <div className="live-empty">{t("radioRemote.emptyNowPlaying")}</div>
        )}
      </div>
    </div>
  );
}
