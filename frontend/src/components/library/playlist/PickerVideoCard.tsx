"use client";
import React from "react";
import Icon from "@/components/Icon";
import { thumbnailUrl } from "@/lib/thumbnail";
import { formatItemDuration, type Sequencer, type Video } from "./types";

export default function PickerVideoCard({ t, isMobile, video, sequencer, onAdd }: {
  t: (key: string, vars?: Record<string, string | number>) => string; isMobile: boolean; video: Video; sequencer: Sequencer; onAdd: () => void;
}) {
  const { handleDragStart, resetDragState } = sequencer;
  const thumbSrc = thumbnailUrl(video.thumbnail_path);
  return (
    <div
      className={`picker-card ${isMobile ? "always-show-add" : ""}`}
      draggable={!isMobile}
      onDragStart={(e) => handleDragStart(e, video.id, "library")}
      onDragEnd={resetDragState}
      title={video.title}
    >
      <div className="thumbnail-wrapper">
        {thumbSrc ? (
          <img src={thumbSrc} alt="" className="card-thumbnail" />
        ) : (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="movie" size={20} style={{ opacity: 0.25 }} />
          </div>
        )}
        <span className="card-duration" style={{ fontSize: "0.65rem", padding: "1px 4px" }}>
          {formatItemDuration(video.duration_seconds)}
        </span>
      </div>
      <div className="picker-card-content">
        <span className="picker-card-title">{video.title}</span>
        <div className="picker-card-meta">
          {video.program && (
            <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
              {video.program}
            </span>
          )}
          {video.release && (
            <span className="release-badge" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
              {t("playlists.releaseBadge", { release: video.release })}
            </span>
          )}
        </div>
      </div>
      <button
        type="button"
        className="picker-card-add"
        onClick={(e) => {
          e.stopPropagation();
          onAdd();
        }}
        title={t("playlists.addShort")}
      >
        <Icon name="add" size={16} />
      </button>
    </div>
  );
}
