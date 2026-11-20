"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import SearchBox from "@/components/SearchBox";
import PlaylistCard from "@/components/playlist-list/PlaylistCard";
import { matchesQuery } from "@/lib/searchText";

export interface PlaylistSummary {
  id: number;
  name: string;
  created_at: string;
  item_count: number;
  total_duration_seconds: number;
}

interface PlaylistListProps {
  prefix: "playlists" | "audioPlaylists";
  t: (key: string, vars?: Record<string, string | number>) => string;
  isMobile: boolean;
  loading: boolean;
  playlists: PlaylistSummary[];
  selectedPlaylistId: number | null;
  isCreating: boolean;
  handleCreateOpen: () => void;
  handleSelectPlaylist: (playlist: PlaylistSummary) => void;
  handleLaunch: (e: React.MouseEvent, id: number) => void;
  handleDuplicate: (e: React.MouseEvent, id: number) => void;
  triggerDelete: (e: React.MouseEvent, playlist: PlaylistSummary) => void;
}

export default function PlaylistList({
  prefix, t, isMobile, loading, playlists, selectedPlaylistId, isCreating,
  handleCreateOpen, handleSelectPlaylist, handleLaunch, handleDuplicate, triggerDelete,
}: PlaylistListProps) {
  const withSubtitle = prefix === "playlists";
  const [playlistSearch, setPlaylistSearch] = useState<string>("");
  const filteredPlaylists = playlists.filter((p) => matchesQuery(p.name, playlistSearch));
  return (
        <div
          className="playlists-left-panel"
          style={isMobile ? { maxWidth: "100%", minWidth: 0, height: "auto" } : undefined}
        >
          <h3 style={{ fontSize: "1.1rem", margin: withSubtitle ? "0 0 4px" : "0 0 16px", color: "var(--text-main)", fontWeight: 800 }}>
            {t(`${prefix}.title`)}
          </h3>
          {withSubtitle && (
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: "0 0 16px" }}>
              {t(`${prefix}.subtitle`)}
            </p>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "16px" }}>
            <SearchBox
              className="form-control"
              placeholder={t(`${prefix}.searchPlaceholder`)}
              value={playlistSearch}
              onChange={setPlaylistSearch}
              suggestions={playlists.map((p) => p.name)}
              style={{ height: "38px", fontSize: "0.85rem" }}
            />
            <button className="btn btn-primary" onClick={handleCreateOpen} style={{ width: "100%", height: "38px" }}>
              <Icon name="add" size={18} />
              {t(`${prefix}.createPlaylist`)}
            </button>
          </div>

          <div className="playlists-scroll-area" style={isMobile ? { maxHeight: "260px" } : undefined}>
            {loading ? (
              <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)", fontSize: "0.9rem" }}>
                {t(`${prefix}.loading`)}
              </div>
            ) : filteredPlaylists.length === 0 ? (
              <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                {t(`${prefix}.noPlaylistsFound`)}
              </div>
            ) : (
              filteredPlaylists.map((p) => (
                <PlaylistCard
                  key={p.id}
                  playlist={p}
                  prefix={prefix}
                  t={t}
                  active={selectedPlaylistId === p.id && !isCreating}
                  onSelect={handleSelectPlaylist}
                  onLaunch={handleLaunch}
                  onDuplicate={handleDuplicate}
                  onDelete={triggerDelete}
                />
              ))
            )}
          </div>
        </div>
  );
}
