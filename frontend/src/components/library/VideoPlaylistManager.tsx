"use client";
import { errorMessage } from "@/lib/apiError";

import React, { useCallback, useEffect, useState } from "react";
import { usePlaylistSequencer } from "@/lib/usePlaylistSequencer";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useIsMobile } from "@/lib/useIsMobile";
import Icon from "@/components/Icon";
import PlaylistList from "@/components/PlaylistList";
import VideoPicker from "./playlist/VideoPicker";
import VideoSequencer from "./playlist/VideoSequencer";
import type { PlaylistDetail, PlaylistItemInput, PlaylistSummary, Video } from "./playlist/types";
import { getApiUrl } from "@/lib/apiUrl";
import { formatMinutes } from "@/lib/format";
import { useToast } from "@/lib/useToast";

export default function VideoPlaylistManager() {
  const { t } = useAppSettings();
  const isMobile = useIsMobile();
  const { connected, sendCommand } = usePlaybackSocket();
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const { toast, showToast } = useToast();

  const [selectedPlaylistId, setSelectedPlaylistId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [playlistName, setPlaylistName] = useState<string>("");
  const [playlistItems, setPlaylistItems] = useState<Video[]>([]);

  const sequencer = usePlaylistSequencer(setPlaylistItems, (id) => videos.find((v) => v.id === id));
  const [isSaving, setIsSaving] = useState<boolean>(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [playlistToDelete, setPlaylistToDelete] = useState<PlaylistSummary | null>(null);

  const fetchPlaylists = useCallback(() => fetch(getApiUrl("/playlists"), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setPlaylists(await res.json());
      else showToast(t("playlists.fetchError"), "error");
    })
    .catch(() => showToast(t("playlists.fetchNetworkError"), "error")), [showToast, t]);

  const fetchVideos = useCallback(() => fetch(getApiUrl("/videos?sort_by=imported_at&order=desc"), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setVideos(await res.json());
    })
    .catch(() => showToast(t("playlists.videosNetworkError"), "error")), [showToast, t]);

  useEffect(() => {
    Promise.all([fetchPlaylists(), fetchVideos()]).finally(() => setLoading(false));
  }, [fetchPlaylists, fetchVideos]);

  const handleLaunch = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!connected) {
      showToast(t("playlists.screenDisconnected"), "error");
      return;
    }
    sendCommand("load_playlist", { playlist_id: id });
    showToast(t("playlists.launchedToast"));
  };

  const triggerDelete = (e: React.MouseEvent, playlist: PlaylistSummary) => {
    e.stopPropagation();
    setPlaylistToDelete(playlist);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!playlistToDelete) return;
    try {
      const res = await fetch(getApiUrl(`/playlists/${playlistToDelete.id}`), {
        method: "DELETE",
      });
      if (res.ok) {
        showToast(t("playlists.deletedToast"));
        setPlaylists((prev) => prev.filter((p) => p.id !== playlistToDelete.id));
        if (selectedPlaylistId === playlistToDelete.id) {
          handleCancelEdit();
        }
      } else {
        showToast(t("playlists.deleteError"), "error");
      }
    } catch {
      showToast(t("playlists.deleteNetworkError"), "error");
    } finally {
      setShowDeleteConfirm(false);
      setPlaylistToDelete(null);
    }
  };

  const handleDuplicate = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      const res = await fetch(getApiUrl(`/playlists/${id}/duplicate`), {
        method: "POST",
      });
      if (res.ok) {
        showToast(t("playlists.duplicatedToast"));
        fetchPlaylists();
      } else {
        showToast(t("playlists.duplicateError"), "error");
      }
    } catch {
      showToast(t("playlists.connectionError"), "error");
    }
  };

  const handleCreateOpen = () => {
    setSelectedPlaylistId(null);
    setIsCreating(true);
    setPlaylistName("");
    setPlaylistItems([]);
  };

  const handleSelectPlaylist = async (playlistSummary: PlaylistSummary) => {
    setSelectedPlaylistId(playlistSummary.id);
    setIsCreating(false);
    setPlaylistName(playlistSummary.name);
    setPlaylistItems([]);

    try {
      const res = await fetch(getApiUrl(`/playlists/${playlistSummary.id}`), {
        cache: "no-store",
      });
      if (res.ok) {
        const detail: PlaylistDetail = await res.json();
        const items = detail.items.map((item) => item.video);
        setPlaylistItems(items);
      } else {
        showToast(t("playlists.detailFetchError"), "error");
      }
    } catch {
      showToast(t("playlists.networkError"), "error");
    }
  };

  const handleCancelEdit = () => {
    setSelectedPlaylistId(null);
    setIsCreating(false);
    setPlaylistName("");
    setPlaylistItems([]);
  };

  const handleAddVideo = (video: Video) => {
    setPlaylistItems((prev) => [...prev, video]);
    showToast(t("playlists.addedToast", { title: video.title }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!playlistName.trim()) {
      showToast(t("playlists.emptyNameWarning"), "warning");
      return;
    }

    setIsSaving(true);
    const itemsPayload: PlaylistItemInput[] = playlistItems.map((video, index) => ({
      video_id: video.id,
      position: index,
    }));

    try {
      const url = selectedPlaylistId
        ? getApiUrl(`/playlists/${selectedPlaylistId}`)
        : getApiUrl("/playlists");
      const method = selectedPlaylistId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: playlistName.trim(),
          items: itemsPayload,
        }),
      });

      if (res.ok) {
        showToast(
          selectedPlaylistId
            ? t("playlists.updatedToast")
            : t("playlists.createdToast")
        );
        fetchPlaylists();
        if (!selectedPlaylistId) {
          const newPlaylistsRes = await fetch(getApiUrl("/playlists"), { cache: "no-store" });
          if (newPlaylistsRes.ok) {
            const newList: PlaylistSummary[] = await newPlaylistsRes.json();
            const created = newList.find((p) => p.name === playlistName.trim());
            if (created) {
              handleSelectPlaylist(created);
            } else {
              handleCancelEdit();
            }
          } else {
            handleCancelEdit();
          }
        } else {
          const activeSummary = playlists.find((p) => p.id === selectedPlaylistId);
          if (activeSummary) {
            handleSelectPlaylist({
              ...activeSummary,
              name: playlistName.trim(),
            });
          }
        }
      } else {
        const data = await res.json();
        showToast(errorMessage(data, t("playlists.saveError")), "error");
      }
    } catch {
      showToast(t("playlists.saveConnectionError"), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const totalDurationSeconds = playlistItems.reduce(
    (acc, item) => acc + (item.duration_seconds ?? 0),
    0
  );

  return (
    <div className="playlist-manager-wrap">
      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.type === "success" && <Icon name="check_circle" size={20} color="var(--accent-success-text)" filled />}
          {toast.type === "error" && <Icon name="error" size={20} color="var(--accent-error-text)" filled />}
          {toast.type === "warning" && <Icon name="warning" size={20} color="var(--accent-warning-text)" filled />}
          <span>{toast.message}</span>
        </div>
      )}

      <div
        className="playlists-split-container"
        style={isMobile ? { flexDirection: "column", height: "auto", overflow: "visible" } : undefined}
      >
        <PlaylistList
          prefix="playlists" t={t} isMobile={isMobile} loading={loading} playlists={playlists}
          selectedPlaylistId={selectedPlaylistId} isCreating={isCreating}
          handleCreateOpen={handleCreateOpen} handleSelectPlaylist={handleSelectPlaylist}
          handleLaunch={handleLaunch} handleDuplicate={handleDuplicate} triggerDelete={triggerDelete}
        />

        <div
          className="playlists-right-panel"
          style={isMobile ? { minWidth: 0, height: "auto", overflow: "visible" } : undefined}
        >
          {selectedPlaylistId === null && !isCreating ? (
            <div className="editor-placeholder">
              <Icon name="edit_note" size={48} color="var(--border-focus)" style={{ marginBottom: "12px" }} />
              <h4 style={{ margin: 0, fontWeight: 700, color: "var(--text-main)" }}>{t("playlists.editorTitle")}</h4>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
                {t("playlists.editorPlaceholderHint")}
              </p>
            </div>
          ) : (
            <form onSubmit={handleSave} className="playlist-editor-form" style={isMobile ? { height: "auto" } : undefined}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>
                  {isCreating ? t("playlists.newPlaylist") : t("playlists.editPlaylist")}
                </h3>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ height: "36px", padding: "0 16px", fontSize: "0.85rem" }}
                    disabled={isSaving}
                  >
                    {isSaving ? t("common.saving") : t("playlists.save")}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ height: "36px", padding: "0 16px", fontSize: "0.85rem" }}
                    onClick={handleCancelEdit}
                    disabled={isSaving}
                  >
                    {t("common.cancel")}
                  </button>
                </div>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: "0.75rem", marginBottom: "4px" }}>
                  {t("playlists.nameLabel")}
                </label>
                <input
                  type="text"
                  className="form-control"
                  placeholder={t("playlists.namePlaceholder")}
                  value={playlistName}
                  onChange={(e) => setPlaylistName(e.target.value)}
                  required
                  disabled={isSaving}
                  style={{ height: "40px" }}
                />
              </div>

              <div className="editor-metadata-grid" style={isMobile ? { gridTemplateColumns: "1fr 1fr" } : undefined}>
                <div className="metadata-stat">
                  <span className="metadata-stat-label">{t("playlists.courseCountLabel")}</span>
                  <span className="metadata-stat-value">{playlistItems.length}</span>
                </div>
                <div className="metadata-stat">
                  <span className="metadata-stat-label">{t("playlists.totalDurationLabel")}</span>
                  <span className="metadata-stat-value">{formatMinutes(totalDurationSeconds, "0 min")}</span>
                </div>
                <div className="metadata-stat">
                  <span className="metadata-stat-label">{t("playlists.statusLabel")}</span>
                  <span className="metadata-stat-value" style={{ color: "var(--accent-text)", fontSize: "0.95rem", textTransform: "uppercase" }}>
                    {t("playlists.statusEditing")}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px", flex: "1 0 auto" }}>
                <span className="form-label" style={{ fontSize: "0.75rem", margin: 0 }}>
                  {t("playlists.sequencerLabel")}
                </span>

                <VideoSequencer t={t} isMobile={isMobile} playlistItems={playlistItems} sequencer={sequencer} />
              </div>

              <VideoPicker
                key={selectedPlaylistId ?? "new"}
                t={t} isMobile={isMobile} videos={videos} sequencer={sequencer} handleAddVideo={handleAddVideo}
              />
            </form>
          )}
        </div>
      </div>

      {showDeleteConfirm && playlistToDelete && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", margin: "0 0 12px" }}>{t("playlists.deletePlaylistTitle")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: "0 0 20px", lineHeight: 1.5 }}>
              {t("playlists.deletePlaylistConfirmBefore")} <strong style={{ color: "var(--text-main)" }}>{playlistToDelete.name}</strong>{t("playlists.deletePlaylistConfirmAfter")}
            </p>
            <div className="modal-actions">
              <button className="btn btn-danger" onClick={confirmDelete}>
                {t("common.delete")}
              </button>
              <button className="btn btn-secondary" onClick={() => {
                setShowDeleteConfirm(false);
                setPlaylistToDelete(null);
              }}>
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
