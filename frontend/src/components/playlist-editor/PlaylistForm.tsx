"use client";

import React from "react";
import { formatMinutes } from "@/lib/format";
import type { PlaylistEditorLayoutProps } from "./PlaylistEditorLayout";

const ACTION: React.CSSProperties = { height: "36px", padding: "0 16px", fontSize: "0.85rem" };

export default function PlaylistForm<Item>({ editor, prefix, t, isMobile, totalDurationSeconds, statusOnMobile, sequencer, picker }: PlaylistEditorLayoutProps<Item>) {
  const { draft, isSaving } = editor;
  const label = (key: string) => t(`${prefix}.${key}`);
  return (
    <form onSubmit={editor.save} className="playlist-editor-form" style={isMobile ? { height: "auto" } : undefined}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>
          {draft.isCreating ? label("newPlaylist") : label("editPlaylist")}
        </h3>
        <div style={{ display: "flex", gap: "8px" }}>
          <button type="submit" className="btn btn-primary" style={ACTION} disabled={isSaving}>
            {isSaving ? t("common.saving") : label("save")}
          </button>
          <button type="button" className="btn btn-secondary" style={ACTION} onClick={draft.cancel} disabled={isSaving}>
            {t("common.cancel")}
          </button>
        </div>
      </div>

      <div className="form-group" style={{ margin: 0 }}>
        <label className="form-label" style={{ fontSize: "0.75rem", marginBottom: "4px" }}>{label("nameLabel")}</label>
        <input
          type="text"
          className="form-control"
          placeholder={label("namePlaceholder")}
          value={draft.playlistName}
          onChange={(e) => draft.setPlaylistName(e.target.value)}
          required
          disabled={isSaving}
          style={{ height: "40px" }}
        />
      </div>

      <div className="editor-metadata-grid" style={isMobile ? { gridTemplateColumns: "1fr 1fr" } : undefined}>
        <div className="metadata-stat">
          <span className="metadata-stat-label">{label("courseCountLabel")}</span>
          <span className="metadata-stat-value">{draft.playlistItems.length}</span>
        </div>
        <div className="metadata-stat">
          <span className="metadata-stat-label">{label("totalDurationLabel")}</span>
          <span className="metadata-stat-value">{formatMinutes(totalDurationSeconds, "0 min")}</span>
        </div>
        {(statusOnMobile || !isMobile) && (
          <div className="metadata-stat">
            <span className="metadata-stat-label">{label("statusLabel")}</span>
            <span className="metadata-stat-value" style={{ color: "var(--accent-text)", fontSize: "0.95rem", textTransform: "uppercase" }}>
              {label("statusEditing")}
            </span>
          </div>
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px", flex: "1 0 auto" }}>
        <span className="form-label" style={{ fontSize: "0.75rem", margin: 0 }}>{label("sequencerLabel")}</span>
        {sequencer}
      </div>

      {picker}
    </form>
  );
}
