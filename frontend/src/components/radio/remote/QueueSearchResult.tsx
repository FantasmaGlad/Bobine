"use client";

import React from "react";
import Highlight from "@/components/Highlight";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { formatTime } from "@/lib/format";
import type { RadioTrackSearchResult, SendRadioCommand } from "./types";

const SMALL_BUTTON: React.CSSProperties = { height: "30px", padding: "0 10px", fontSize: "0.75rem" };

export default function QueueSearchResult({ track, query, sendCommand }: { track: RadioTrackSearchResult; query: string; sendCommand: SendRadioCommand }) {
  const { t } = useAppSettings();
  return (
    <div className="rq-row">
      {track.has_cover ? (
        <img className="rq-cover" src={getApiUrl(`/radio/tracks/${track.id}/cover`)} alt="" loading="lazy" />
      ) : (
        <span className="rq-cover rq-cover--empty" aria-hidden="true">
          <Icon name="music_note" size={20} style={{ opacity: 0.4 }} />
        </span>
      )}
      <span className="rq-text">
        <span className="rq-title">
          <Highlight text={track.title} query={query} />
        </span>
        <span className="rq-sub">
          <span className="rq-artist">
            <Highlight text={track.artist || t("radioLibrary.unknownArtist")} query={query} />
          </span>
          {track.genre ? <span className="rq-genre">{track.genre}</span> : null}
        </span>
      </span>
      <span className="rq-duration">{formatTime(track.duration_seconds)}</span>
      <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
        <button className="btn btn-secondary" style={SMALL_BUTTON} title={t("radioRemote.playNextHint")} onClick={() => sendCommand("radio_play_next", { track_id: track.id })}>
          <Icon name="playlist_play" size={14} />
          {t("radioRemote.playNext")}
        </button>
        <button className="btn btn-secondary" style={SMALL_BUTTON} title={t("radioRemote.addToQueueHint")} onClick={() => sendCommand("radio_add_to_queue", { track_id: track.id })}>
          <Icon name="add" size={14} />
          {t("radioRemote.add")}
        </button>
      </div>
    </div>
  );
}
