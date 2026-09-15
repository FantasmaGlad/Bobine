"use client";

import React, { useEffect, useState } from "react";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useIsMobile } from "@/lib/useIsMobile";
import Icon from "@/components/Icon";

interface Video {
  id: number;
  title: string;
  program: string | null;
  release: string | null;
  duration_seconds: number | null;
  thumbnail_path: string | null;
}

interface PlaylistItemInput {
  video_id: number;
  position: number;
}

interface PlaylistItemResponse {
  id: number;
  position: number;
  video: Video;
}

interface PlaylistDetail {
  id: number;
  name: string;
  created_at: string;
  items: PlaylistItemResponse[];
  total_duration_seconds: number;
}

interface PlaylistSummary {
  id: number;
  name: string;
  created_at: string;
  item_count: number;
  total_duration_seconds: number;
}

interface ToastState {
  message: string;
  type: "success" | "error" | "warning";
}

/**
 * Créateur de playlists vidéo pour le mode kiosk, embarqué dans l'onglet
 * "Playlists" de la Bibliothèque (réf. mission "supprimer la catégorie
 * playlist du volet ouvrant, déplacer la création de playlist vidéo dans
 * Bibliothèque") — anciennement la page `/playlists` à part entière.
 *
 * Le panneau "Ajouter depuis la bibliothèque" affiche désormais des cartes
 * avec vignette (réf. mission "sans devoir chercher à l'aveugle dans un
 * énorme catalogue sans preview ni image") au lieu de simples lignes de
 * texte.
 */
export default function VideoPlaylistManager() {
  const { t } = useAppSettings();
  const isMobile = useIsMobile();
  const { connected, sendCommand } = usePlaybackSocket();
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [toast, setToast] = useState<ToastState | null>(null);

  const [playlistSearch, setPlaylistSearch] = useState<string>("");

  const [videoSearch, setVideoSearch] = useState<string>("");
  const [videoProgramFilter, setVideoProgramFilter] = useState<string>("");

  const [selectedPlaylistId, setSelectedPlaylistId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [playlistName, setPlaylistName] = useState<string>("");
  const [playlistItems, setPlaylistItems] = useState<Video[]>([]);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [draggedVideoId, setDraggedVideoId] = useState<number | null>(null);
  const [dragSource, setDragSource] = useState<"sequencer" | "library" | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [playlistToDelete, setPlaylistToDelete] = useState<PlaylistSummary | null>(null);

  const getApiUrl = (path: string) => {
    if (typeof window !== "undefined") {
      if (window.location.port === "3000") {
        return `http://localhost:8001/api${path}`;
      }
    }
    return `/api${path}`;
  };

  const showToast = (message: string, type: "success" | "error" | "warning" = "success") => {
    setToast({ message, type });
  };

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => {
        setToast(null);
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const fetchPlaylists = async () => {
    try {
      const res = await fetch(getApiUrl("/playlists"), { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setPlaylists(data);
      } else {
        showToast(t("playlists.fetchError"), "error");
      }
    } catch {
      showToast(t("playlists.fetchNetworkError"), "error");
    }
  };

  const fetchVideos = async () => {
    try {
      const res = await fetch(getApiUrl("/videos?sort_by=imported_at&order=desc"), { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setVideos(data);
      }
    } catch {
      showToast(t("playlists.videosNetworkError"), "error");
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    Promise.all([fetchPlaylists(), fetchVideos()]).finally(() => setLoading(false));
  }, []);

  const formatDuration = (seconds: number) => {
    if (!seconds) return "0 min";
    const mins = Math.round(seconds / 60);
    return `${mins} min`;
  };

  const formatItemDuration = (seconds: number | null) => {
    if (seconds === null || seconds === undefined) return "--:--";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const getThumbnailSrc = (video: Video) => {
    if (!video.thumbnail_path) return null;
    const filename = video.thumbnail_path.split("/").pop();
    if (!filename) return null;
    return getApiUrl(`/thumbnails/${filename}`);
  };

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
    setVideoSearch("");
    setVideoProgramFilter("");
  };

  const handleSelectPlaylist = async (playlistSummary: PlaylistSummary) => {
    setSelectedPlaylistId(playlistSummary.id);
    setIsCreating(false);
    setPlaylistName(playlistSummary.name);
    setPlaylistItems([]);
    setVideoSearch("");
    setVideoProgramFilter("");

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

  const handleRemoveVideo = (index: number) => {
    setPlaylistItems((prev) => prev.filter((_, i) => i !== index));
  };

  const handleMoveUp = (index: number) => {
    if (index === 0) return;
    setPlaylistItems((prev) => {
      const copy = [...prev];
      const temp = copy[index];
      copy[index] = copy[index - 1];
      copy[index - 1] = temp;
      return copy;
    });
  };

  const handleMoveDown = (index: number) => {
    setPlaylistItems((prev) => {
      if (index === prev.length - 1) return prev;
      const copy = [...prev];
      const temp = copy[index];
      copy[index] = copy[index + 1];
      copy[index + 1] = temp;
      return copy;
    });
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
        showToast(data.detail || t("playlists.saveError"), "error");
      }
    } catch {
      showToast(t("playlists.saveConnectionError"), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDragStart = (e: React.DragEvent, indexOrId: number, source: "sequencer" | "library") => {
    setDragSource(source);
    if (source === "sequencer") {
      setDraggedIndex(indexOrId);
      e.dataTransfer.setData("text/plain", indexOrId.toString());
    } else {
      setDraggedVideoId(indexOrId);
      e.dataTransfer.setData("text/plain", indexOrId.toString());
    }
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleDrop = (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    if (dragSource === "sequencer" && draggedIndex !== null) {
      if (draggedIndex !== targetIndex) {
        setPlaylistItems((prev) => {
          const copy = [...prev];
          const [moved] = copy.splice(draggedIndex, 1);
          copy.splice(targetIndex, 0, moved);
          return copy;
        });
      }
    } else if (dragSource === "library" && draggedVideoId !== null) {
      const video = videos.find((v) => v.id === draggedVideoId);
      if (video) {
        setPlaylistItems((prev) => {
          const copy = [...prev];
          copy.splice(targetIndex, 0, video);
          return copy;
        });
      }
    }
    resetDragState();
  };

  const handleDropOnEmptyZone = (e: React.DragEvent) => {
    e.preventDefault();
    if (dragSource === "library" && draggedVideoId !== null) {
      const video = videos.find((v) => v.id === draggedVideoId);
      if (video) {
        setPlaylistItems((prev) => [...prev, video]);
      }
    }
    resetDragState();
  };

  const resetDragState = () => {
    setDraggedIndex(null);
    setDraggedVideoId(null);
    setDragSource(null);
    setDragOverIndex(null);
  };

  const availablePrograms = React.useMemo(() => {
    const set = new Set<string>();
    for (const v of videos) if (v.program) set.add(v.program);
    return Array.from(set).sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));
  }, [videos]);

  const filteredPlaylists = playlists.filter((p) =>
    p.name.toLowerCase().includes(playlistSearch.toLowerCase())
  );

  const filteredVideos = videos.filter((v) => {
    const matchesSearch =
      v.title.toLowerCase().includes(videoSearch.toLowerCase()) ||
      (v.release && v.release.includes(videoSearch));
    const matchesProgram = !videoProgramFilter || v.program === videoProgramFilter;
    return matchesSearch && matchesProgram;
  });

  const totalDurationSeconds = playlistItems.reduce(
    (acc, item) => acc + (item.duration_seconds ?? 0),
    0
  );

  return (
    <div className="playlist-manager-wrap">
      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.type === "success" && <Icon name="check_circle" size={20} color="var(--accent-success)" filled />}
          {toast.type === "error" && <Icon name="error" size={20} color="var(--accent-error)" filled />}
          {toast.type === "warning" && <Icon name="warning" size={20} color="var(--accent-warning)" filled />}
          <span>{toast.message}</span>
        </div>
      )}

      <div
        className="playlists-split-container"
        style={isMobile ? { flexDirection: "column", height: "auto", overflow: "visible" } : undefined}
      >
        {/* Left Panel: Search & Playlists list */}
        <div
          className="playlists-left-panel"
          style={isMobile ? { maxWidth: "100%", minWidth: 0, height: "auto" } : undefined}
        >
          <h3 style={{ fontSize: "1.1rem", margin: "0 0 4px", color: "var(--text-main)", fontWeight: 800 }}>
            {t("playlists.title")}
          </h3>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: "0 0 16px" }}>
            {t("playlists.subtitle")}
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "16px" }}>
            <input
              type="text"
              className="form-control"
              placeholder={t("playlists.searchPlaceholder")}
              value={playlistSearch}
              onChange={(e) => setPlaylistSearch(e.target.value)}
              style={{ height: "38px", fontSize: "0.85rem" }}
            />
            <button className="btn btn-primary" onClick={handleCreateOpen} style={{ width: "100%", height: "38px" }}>
              <Icon name="add" size={18} />
              {t("playlists.createPlaylist")}
            </button>
          </div>

          <div className="playlists-scroll-area" style={isMobile ? { maxHeight: "260px" } : undefined}>
            {loading ? (
              <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)", fontSize: "0.9rem" }}>
                {t("playlists.loading")}
              </div>
            ) : filteredPlaylists.length === 0 ? (
              <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                {t("playlists.noPlaylistsFound")}
              </div>
            ) : (
              filteredPlaylists.map((p) => {
                const isActiveCard = selectedPlaylistId === p.id && !isCreating;
                return (
                  <div
                    key={p.id}
                    className={`playlist-card ${isActiveCard ? "active" : ""}`}
                    onClick={() => handleSelectPlaylist(p)}
                  >
                    <div className="playlist-card-header">
                      <span className="playlist-card-title">{p.name}</span>
                    </div>
                    <div className="playlist-card-meta">
                      <span className="release-badge" style={{ padding: "2px 6px" }}>
                        {t("playlists.coursesCount", { count: p.item_count })}
                      </span>
                      <span>{formatDuration(p.total_duration_seconds)}</span>
                    </div>
                    <div className="playlist-card-actions">
                      <button
                        className="btn btn-primary"
                        style={{ height: "28px", padding: "0 10px", fontSize: "0.75rem" }}
                        onClick={(e) => handleLaunch(e, p.id)}
                        title={t("playlists.launch")}
                      >
                        <Icon name="play_arrow" size={14} filled />
                        {t("playlists.launch")}
                      </button>
                      <button
                        className="btn btn-secondary"
                        style={{ height: "28px", padding: "0 8px", fontSize: "0.75rem" }}
                        onClick={(e) => handleDuplicate(e, p.id)}
                        title={t("playlists.duplicate")}
                      >
                        <Icon name="content_copy" size={14} />
                        {t("playlists.duplicate")}
                      </button>
                      <button
                        className="btn btn-danger"
                        style={{ height: "28px", padding: "0 8px", fontSize: "0.75rem" }}
                        onClick={(e) => triggerDelete(e, p)}
                        title={t("common.delete")}
                      >
                        <Icon name="delete" size={14} />
                        {t("common.delete")}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Panel: Editor or Placeholder */}
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
                  <span className="metadata-stat-value">{formatDuration(totalDurationSeconds)}</span>
                </div>
                <div className="metadata-stat">
                  <span className="metadata-stat-label">{t("playlists.statusLabel")}</span>
                  <span className="metadata-stat-value" style={{ color: "var(--accent-primary)", fontSize: "0.95rem", textTransform: "uppercase" }}>
                    {t("playlists.statusEditing")}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px", flex: "1 0 auto" }}>
                <span className="form-label" style={{ fontSize: "0.75rem", margin: 0 }}>
                  {t("playlists.sequencerLabel")}
                </span>

                <div
                  className={`drag-drop-zone ${dragOverIndex === -1 ? "drag-over" : ""}`}
                  style={isMobile ? { minHeight: "80px", maxHeight: "320px" } : undefined}
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (dragSource === "library") setDragOverIndex(-1);
                  }}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDropOnEmptyZone}
                >
                  {playlistItems.length === 0 ? (
                    <div className="empty-playlist-placeholder">
                      <Icon name="playlist_add" size={32} color="var(--border-focus)" />
                      <span>{t("playlists.emptySequencer")}</span>
                      <span style={{ fontSize: "0.75rem", opacity: 0.7 }}>{t("playlists.emptySequencerHint")}</span>
                    </div>
                  ) : (
                    playlistItems.map((item, index) => {
                      const isDragged = draggedIndex === index && dragSource === "sequencer";
                      const isOver = dragOverIndex === index;
                      return (
                        <div
                          key={`${item.id}-${index}`}
                          className={`playlist-drag-item ${isDragged ? "dragging" : ""} ${isOver ? "drag-over-item" : ""}`}
                          draggable={!isMobile}
                          onDragStart={(e) => handleDragStart(e, index, "sequencer")}
                          onDragOver={(e) => handleDragOver(e, index)}
                          onDragLeave={handleDragLeave}
                          onDrop={(e) => handleDrop(e, index)}
                          onDragEnd={resetDragState}
                        >
                          {!isMobile && <div className="drag-handle"><Icon name="drag_indicator" size={16} /></div>}
                          <span style={{ fontWeight: 800, color: "var(--text-muted)", fontSize: "0.85rem", width: "16px" }}>
                            {index + 1}
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--text-main)", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                              {item.title}
                            </div>
                            <div style={{ display: "flex", gap: "6px", alignItems: "center", marginTop: "1px" }}>
                              {item.program && (
                                <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                                  {item.program}
                                </span>
                              )}
                              {item.release && (
                                <span className="release-badge" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                                  {t("playlists.releaseBadge", { release: item.release })}
                                </span>
                              )}
                              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                                {formatItemDuration(item.duration_seconds)}
                              </span>
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "4px" }}>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleMoveUp(index)}
                              disabled={index === 0}
                              title={t("playlists.moveUp")}
                            >
                              <Icon name="arrow_upward" size={14} />
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleMoveDown(index)}
                              disabled={index === playlistItems.length - 1}
                              title={t("playlists.moveDown")}
                            >
                              <Icon name="arrow_downward" size={14} />
                            </button>
                            <button
                              type="button"
                              className="btn btn-danger"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleRemoveVideo(index)}
                              title={t("playlists.remove")}
                            >
                              <Icon name="close" size={14} />
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Library Picker at the Bottom : grille de vignettes plutôt que
                  du texte (réf. mission "sans image, à l'aveugle"). */}
              <div className="library-picker" style={isMobile ? { height: "auto", maxHeight: "360px" } : undefined}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="form-label" style={{ fontSize: "0.75rem", margin: 0, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}>
                    {t("playlists.libraryPickerLabel")}
                  </span>
                </div>

                <div style={{ display: "flex", gap: "8px", flexWrap: isMobile ? "wrap" : "nowrap" }}>
                  <input
                    type="text"
                    className="form-control"
                    style={{ flex: 1, height: "32px", fontSize: "0.8rem", padding: "0 10px", minWidth: isMobile ? "100%" : undefined }}
                    placeholder={t("playlists.videoSearchPlaceholder")}
                    value={videoSearch}
                    onChange={(e) => setVideoSearch(e.target.value)}
                  />
                  <select
                    className="filter-select"
                    style={{ height: "32px", fontSize: "0.8rem", padding: "0 8px" }}
                    value={videoProgramFilter}
                    onChange={(e) => setVideoProgramFilter(e.target.value)}
                  >
                    <option value="">{t("playlists.allProgramsShort")}</option>
                    {availablePrograms.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>

                <div className="library-picker-list">
                  {filteredVideos.length === 0 ? (
                    <div style={{ gridColumn: "1 / -1", textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem", padding: "16px" }}>
                      {t("playlists.noMatchingVideos")}
                    </div>
                  ) : (
                    filteredVideos.map((video) => {
                      const thumbSrc = getThumbnailSrc(video);
                      return (
                        <div
                          key={video.id}
                          className={`picker-card ${isMobile ? "always-show-add" : ""}`}
                          draggable={!isMobile}
                          onDragStart={(e) => handleDragStart(e, video.id, "library")}
                          onDragEnd={resetDragState}
                          title={video.title}
                        >
                          <div className="thumbnail-wrapper">
                            {thumbSrc ? (
                              // eslint-disable-next-line @next/next/no-img-element
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
                              handleAddVideo(video);
                            }}
                            title={t("playlists.addShort")}
                          >
                            <Icon name="add" size={16} />
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
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
