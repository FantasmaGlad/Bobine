"use client";

import React from "react";
import Icon from "@/components/Icon";
import type { PlaylistSummary } from "@/components/PlaylistList";
import { formatMinutes } from "@/lib/format";

interface CardProps {
  playlist: PlaylistSummary;
  prefix: "playlists" | "audioPlaylists";
  t: (key: string, vars?: Record<string, string | number>) => string;
  active: boolean;
  onSelect: (playlist: PlaylistSummary) => void;
  onLaunch: (e: React.MouseEvent, id: number) => void;
  onDuplicate: (e: React.MouseEvent, id: number) => void;
  onDelete: (e: React.MouseEvent, playlist: PlaylistSummary) => void;
}

export default function PlaylistCard({ playlist: p, prefix, t, active, onSelect, onLaunch, onDuplicate, onDelete }: CardProps) {
  return (
    <div
      className={`playlist-card ${active ? "active" : ""}`}
      onClick={() => onSelect(p)}
    >
      <div className="playlist-card-header">
        <span className="playlist-card-title">{p.name}</span>
      </div>
      <div className="playlist-card-meta">
        <span className="release-badge" style={{ padding: "2px 6px" }}>
          {t(`${prefix}.coursesCount`, { count: p.item_count })}
        </span>
        <span>{formatMinutes(p.total_duration_seconds, "0 min")}</span>
      </div>
      <div className="playlist-card-actions">
        <button
          className="btn btn-primary"
          style={{ height: "28px", padding: "0 10px", fontSize: "0.75rem" }}
          onClick={(e) => onLaunch(e, p.id)}
          title={t(`${prefix}.launch`)}
        >
          <Icon name="play_arrow" size={14} filled />
          {t(`${prefix}.launch`)}
        </button>
        <button
          className="btn btn-secondary"
          style={{ height: "28px", padding: "0 8px", fontSize: "0.75rem" }}
          onClick={(e) => onDuplicate(e, p.id)}
          title={t(`${prefix}.duplicate`)}
        >
          <Icon name="content_copy" size={14} />
          {t(`${prefix}.duplicate`)}
        </button>
        <button
          className="btn btn-danger"
          style={{ height: "28px", padding: "0 8px", fontSize: "0.75rem" }}
          onClick={(e) => onDelete(e, p)}
          title={t("common.delete")}
        >
          <Icon name="delete" size={14} />
          {t("common.delete")}
        </button>
      </div>
    </div>
  );
}
