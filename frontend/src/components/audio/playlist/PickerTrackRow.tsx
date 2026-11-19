"use client";

import React from "react";
import Icon from "@/components/Icon";
import { formatMediaDuration } from "@/lib/format";
import type { AudioTrackSummary, Sequencer } from "./types";

export default function PickerTrackRow({ t, isMobile, track, sequencer, onAdd }: {
  t: (key: string) => string; isMobile: boolean; track: AudioTrackSummary; sequencer: Sequencer; onAdd: () => void;
}) {
  const { handleDragStart, resetDragState } = sequencer;
  return (
    <div
        className="picker-track-row"
      draggable={!isMobile}
      onDragStart={(e) => handleDragStart(e, track.id, "library")}
      onDragEnd={resetDragState}
    >
      {!isMobile && <div className="drag-handle" style={{ padding: 0 }}><Icon name="drag_indicator" size={14} /></div>}
      <span style={{ flex: 1, minWidth: 0, fontSize: "0.78rem", fontWeight: 600, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {track.number ? `${track.number}. ` : ""}{track.title}
      </span>
      <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", flexShrink: 0 }}>
        {formatMediaDuration(track.duration_seconds)}
      </span>
      <button
        type="button"
        className="btn btn-secondary"
        style={{ height: "22px", padding: "0 6px", fontSize: "0.68rem", fontWeight: 700, flexShrink: 0 }}
        onClick={onAdd}
      >
        {t("audioPlaylists.addShort")}
      </button>
    </div>
  );
}
