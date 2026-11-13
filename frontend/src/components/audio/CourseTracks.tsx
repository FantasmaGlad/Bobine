"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMediaDuration } from "@/lib/format";

import type { AudioTrack, BackgroundOption } from "./types";

interface Props {
  tracks: AudioTrack[];
  backgrounds: BackgroundOption[];
  onReorder: (from: number, to: number) => void;
  onPickBackground: (trackId: number) => void;
}

function AmbianceButton({ background, onClick }: { background: BackgroundOption | null | undefined; onClick: () => void }) {
  const { t } = useAppSettings();
  const on = !!background;
  return (
    <button
      type="button"
      className="olc-press"
      style={{
        display: "inline-flex", alignItems: "center", gap: "6px", padding: "4px 8px", borderRadius: "6px",
        background: on ? "color-mix(in srgb, var(--accent-primary) 15%, var(--bg-surface-elevated))" : "var(--bg-surface)",
        border: `1px solid ${on ? "var(--accent-text)" : "var(--border-color)"}`,
        color: on ? "var(--accent-text)" : "var(--text-muted)", fontSize: "0.75rem", fontWeight: 600, cursor: "pointer", flexShrink: 0,
      }}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        onClick();
      }}
      title={background ? t("audio.trackAmbiance", { title: background.title }) : t("audio.linkAmbiance")}
    >
      <Icon name={background ? (background.is_image ? "image" : "videocam") : "wallpaper"} size={14} />
      <span style={{ maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{background ? background.title : "Ambiance auto"}</span>
    </button>
  );
}

export default function CourseTracks({ tracks, backgrounds, onReorder, onPickBackground }: Props) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const reset = () => {
    setDragIndex(null);
    setOverIndex(null);
  };
  return (
    <div className="drag-drop-zone" style={{ minHeight: "80px" }}>
      {tracks.map((track, index) => (
        <div
          key={track.id}
          className={`playlist-drag-item ${dragIndex === index ? "dragging" : ""} ${overIndex === index ? "drag-over-item" : ""}`}
          draggable
          onDragStart={() => setDragIndex(index)}
          onDragOver={(e) => { e.preventDefault(); setOverIndex(index); }}
          onDrop={() => { if (dragIndex !== null) onReorder(dragIndex, index); reset(); }}
          onDragEnd={reset}
          style={{ display: "flex", alignItems: "center", gap: "10px" }}
        >
          <span className="drag-handle"><Icon name="drag_indicator" size={16} /></span>
          <span style={{ flex: 1, fontWeight: 600, fontSize: "0.88rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{index + 1}. {track.title}</span>
          <AmbianceButton background={track.background_id ? backgrounds.find((b) => b.id === track.background_id) : null} onClick={() => onPickBackground(track.id)} />
          <span style={{ color: "var(--text-muted)", fontSize: "0.8rem", flexShrink: 0 }}>{formatMediaDuration(track.duration_seconds)}</span>
        </div>
      ))}
    </div>
  );
}
