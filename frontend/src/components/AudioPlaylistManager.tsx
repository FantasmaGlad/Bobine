"use client";

import React, { useEffect, useState } from "react";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useIsMobile } from "@/lib/useIsMobile";
import Icon from "@/components/Icon";

interface AudioTrackSummary {
  id: number;
  number: number | null;
  title: string;
  duration_seconds: number | null;
  course_id: number;
  course_title: string;
  course_program: string | null;
}

interface AudioCourseSummary {
  id: number;
  title: string;
  program: string | null;
  background_thumbnail_path: string | null;
  track_count: number;
}

interface AudioPlaylistItemInput {
  audio_track_id: number;
  position: number;
  background_id: number | null;
}

interface AudioPlaylistItemBackground {
  id: number;
  title: string;
  is_image: boolean;
}

interface AudioPlaylistItemResponse {
  id: number;
  position: number;
  track: AudioTrackSummary;
  background: AudioPlaylistItemBackground | null;
}

interface AudioPlaylistDetail {
  id: number;
  name: string;
  created_at: string;
  items: AudioPlaylistItemResponse[];
  total_duration_seconds: number;
}

interface AudioPlaylistSummary {
  id: number;
  name: string;
  created_at: string;
  item_count: number;
  total_duration_seconds: number;
}

interface BackgroundSummary {
  id: number;
  title: string;
  is_image: boolean;
}

/** Un morceau dans le séquenceur, avec son fond d'ambiance propre optionnel
 * (réf. mission "associer un fond animé à chaque musique qui se jouera en
 * arrière plan") — `backgroundId` nul = pas de fond propre, le fond de la
 * playlist/du cours reste affiché pour ce morceau. */
interface PlaylistDraftItem {
  track: AudioTrackSummary;
  backgroundId: number | null;
}

interface ToastState {
  message: string;
  type: "success" | "error" | "warning";
}

function getApiUrl(path: string) {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api${path}`;
  }
  return `/api${path}`;
}

/**
 * Créateur de playlists audio ("éditions mixées") pour le mode coach,
 * embarqué dans l'onglet "Playlists" de Coach → Cours audio (réf. mission
 * "supprimer la catégorie playlist du volet ouvrant, déplacer la création de
 * playlist audio coach dans Coach → Cours audio") — anciennement la page
 * `/audio-playlists` à part entière.
 *
 * Le panneau "Ajouter depuis les cours" affiche des cartes de cours (vignette
 * = ambiance déjà assignée au cours, réf. mission) dépliables en pistes
 * individuelles, PLUS un bouton "tout le cours" pour ajouter d'un coup toutes
 * ses pistes (réf. mission "audio peut contenir des groupes comme des cours
 * entiers, ex. RPM101 = musique 1 à 9") — une piste ajoutée en bloc reste un
 * item indépendant côté serveur, l'ordre suffit à reconstituer le cours.
 */
export default function AudioPlaylistManager() {
  const { t } = useAppSettings();
  const isMobile = useIsMobile();
  const { connected, sendCommand } = usePlaybackSocket();
  const [playlists, setPlaylists] = useState<AudioPlaylistSummary[]>([]);
  const [tracks, setTracks] = useState<AudioTrackSummary[]>([]);
  const [courses, setCourses] = useState<AudioCourseSummary[]>([]);
  const [backgrounds, setBackgrounds] = useState<BackgroundSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [toast, setToast] = useState<ToastState | null>(null);

  const [playlistSearch, setPlaylistSearch] = useState<string>("");
  const [trackSearch, setTrackSearch] = useState<string>("");
  const [trackProgramFilter, setTrackProgramFilter] = useState<string>("");
  const [expandedCourseIds, setExpandedCourseIds] = useState<Set<number>>(new Set());

  const [selectedPlaylistId, setSelectedPlaylistId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [playlistName, setPlaylistName] = useState<string>("");
  const [playlistItems, setPlaylistItems] = useState<PlaylistDraftItem[]>([]);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [draggedTrackId, setDraggedTrackId] = useState<number | null>(null);
  const [dragSource, setDragSource] = useState<"sequencer" | "library" | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [playlistToDelete, setPlaylistToDelete] = useState<AudioPlaylistSummary | null>(null);

  const showToast = (message: string, type: "success" | "error" | "warning" = "success") => {
    setToast({ message, type });
  };

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const fetchPlaylists = async () => {
    try {
      const res = await fetch(getApiUrl("/audio-playlists"), { cache: "no-store" });
      if (res.ok) {
        setPlaylists(await res.json());
      } else {
        showToast(t("audioPlaylists.fetchError"), "error");
      }
    } catch {
      showToast(t("audioPlaylists.fetchNetworkError"), "error");
    }
  };

  const fetchTracks = async () => {
    try {
      const res = await fetch(getApiUrl("/audio/tracks"), { cache: "no-store" });
      if (res.ok) {
        setTracks(await res.json());
      }
    } catch {
      showToast(t("audioPlaylists.coursesNetworkError"), "error");
    }
  };

  const fetchCourses = async () => {
    try {
      const res = await fetch(getApiUrl("/audio"), { cache: "no-store" });
      if (res.ok) {
        setCourses(await res.json());
      }
    } catch {
      // silencieux : les cartes de cours retombent sur l'icône générique
    }
  };

  const fetchBackgrounds = async () => {
    try {
      const res = await fetch(getApiUrl("/backgrounds"), { cache: "no-store" });
      if (res.ok) {
        setBackgrounds(await res.json());
      }
    } catch {
      // Silencieux : le sélecteur de fond par piste reste juste vide.
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    Promise.all([fetchPlaylists(), fetchTracks(), fetchCourses(), fetchBackgrounds()]).finally(() => setLoading(false));
  }, []);

  const formatDuration = (seconds: number) => {
    if (!seconds) return "0 min";
    return `${Math.round(seconds / 60)} min`;
  };

  const formatTrackDuration = (seconds: number | null) => {
    if (!seconds) return "--:--";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const getCourseThumbSrc = (course: AudioCourseSummary) => {
    if (!course.background_thumbnail_path) return null;
    const filename = course.background_thumbnail_path.split("/").pop();
    if (!filename) return null;
    return getApiUrl(`/thumbnails/${filename}`);
  };

  const handleLaunch = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!connected) {
      showToast(t("audioPlaylists.screenDisconnected"), "error");
      return;
    }
    sendCommand("load_audio_playlist", { audio_playlist_id: id });
    showToast(t("audioPlaylists.launchedToast"));
  };

  const triggerDelete = (e: React.MouseEvent, playlist: AudioPlaylistSummary) => {
    e.stopPropagation();
    setPlaylistToDelete(playlist);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!playlistToDelete) return;
    try {
      const res = await fetch(getApiUrl(`/audio-playlists/${playlistToDelete.id}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("audioPlaylists.deletedToast"));
        setPlaylists((prev) => prev.filter((p) => p.id !== playlistToDelete.id));
        if (selectedPlaylistId === playlistToDelete.id) handleCancelEdit();
      } else {
        showToast(t("audioPlaylists.deleteError"), "error");
      }
    } catch {
      showToast(t("audioPlaylists.deleteNetworkError"), "error");
    } finally {
      setShowDeleteConfirm(false);
      setPlaylistToDelete(null);
    }
  };

  const handleDuplicate = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      const res = await fetch(getApiUrl(`/audio-playlists/${id}/duplicate`), { method: "POST" });
      if (res.ok) {
        showToast(t("audioPlaylists.duplicatedToast"));
        fetchPlaylists();
      } else {
        showToast(t("audioPlaylists.duplicateError"), "error");
      }
    } catch {
      showToast(t("audioPlaylists.connectionError"), "error");
    }
  };

  const handleCreateOpen = () => {
    setSelectedPlaylistId(null);
    setIsCreating(true);
    setPlaylistName("");
    setPlaylistItems([]);
    setTrackSearch("");
    setTrackProgramFilter("");
  };

  const handleSelectPlaylist = async (summary: AudioPlaylistSummary) => {
    setSelectedPlaylistId(summary.id);
    setIsCreating(false);
    setPlaylistName(summary.name);
    setPlaylistItems([]);
    setTrackSearch("");
    setTrackProgramFilter("");

    try {
      const res = await fetch(getApiUrl(`/audio-playlists/${summary.id}`), { cache: "no-store" });
      if (res.ok) {
        const detail: AudioPlaylistDetail = await res.json();
        setPlaylistItems(detail.items.map((item) => ({ track: item.track, backgroundId: item.background?.id ?? null })));
      } else {
        showToast(t("audioPlaylists.detailFetchError"), "error");
      }
    } catch {
      showToast(t("audioPlaylists.networkError"), "error");
    }
  };

  const handleCancelEdit = () => {
    setSelectedPlaylistId(null);
    setIsCreating(false);
    setPlaylistName("");
    setPlaylistItems([]);
  };

  const handleAddTrack = (track: AudioTrackSummary) => {
    setPlaylistItems((prev) => [...prev, { track, backgroundId: null }]);
    showToast(t("audioPlaylists.addedToast", { title: track.title }));
  };

  // Réf. mission "audio peut contenir des groupes comme des cours entiers" :
  // ajoute TOUTES les pistes du cours (dans leur ordre d'origine) d'un coup —
  // chacune reste un AudioPlaylistItem indépendant côté serveur, seul l'ordre
  // d'insertion recrée visuellement le "bloc".
  const handleAddWholeCourse = (courseId: number) => {
    const courseTracks = tracks.filter((tr) => tr.course_id === courseId);
    if (courseTracks.length === 0) return;
    setPlaylistItems((prev) => [...prev, ...courseTracks.map((track) => ({ track, backgroundId: null }))]);
    const course = courses.find((c) => c.id === courseId);
    showToast(t("audioPlaylists.addedWholeCourseToast", { title: course?.title ?? "", count: courseTracks.length }));
  };

  const handleRemoveTrack = (index: number) => {
    setPlaylistItems((prev) => prev.filter((_, i) => i !== index));
  };

  const handleMoveUp = (index: number) => {
    if (index === 0) return;
    setPlaylistItems((prev) => {
      const copy = [...prev];
      [copy[index - 1], copy[index]] = [copy[index], copy[index - 1]];
      return copy;
    });
  };

  const handleMoveDown = (index: number) => {
    setPlaylistItems((prev) => {
      if (index === prev.length - 1) return prev;
      const copy = [...prev];
      [copy[index], copy[index + 1]] = [copy[index + 1], copy[index]];
      return copy;
    });
  };

  // Réf. mission "associer un fond animé à chaque musique" : `backgroundId`
  // nul remet le morceau sur le fond par défaut de la playlist/du cours.
  const handleSetTrackBackground = (index: number, backgroundId: number | null) => {
    setPlaylistItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], backgroundId };
      return copy;
    });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!playlistName.trim()) {
      showToast(t("audioPlaylists.emptyNameWarning"), "warning");
      return;
    }

    setIsSaving(true);
    const itemsPayload: AudioPlaylistItemInput[] = playlistItems.map((item, index) => ({
      audio_track_id: item.track.id,
      position: index,
      background_id: item.backgroundId,
    }));

    try {
      const url = selectedPlaylistId
        ? getApiUrl(`/audio-playlists/${selectedPlaylistId}`)
        : getApiUrl("/audio-playlists");
      const method = selectedPlaylistId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: playlistName.trim(), items: itemsPayload }),
      });

      if (res.ok) {
        showToast(selectedPlaylistId ? t("audioPlaylists.updatedToast") : t("audioPlaylists.createdToast"));
        fetchPlaylists();
        if (!selectedPlaylistId) {
          const newListRes = await fetch(getApiUrl("/audio-playlists"), { cache: "no-store" });
          if (newListRes.ok) {
            const newList: AudioPlaylistSummary[] = await newListRes.json();
            const created = newList.find((p) => p.name === playlistName.trim());
            if (created) handleSelectPlaylist(created);
            else handleCancelEdit();
          } else {
            handleCancelEdit();
          }
        } else {
          const activeSummary = playlists.find((p) => p.id === selectedPlaylistId);
          if (activeSummary) handleSelectPlaylist({ ...activeSummary, name: playlistName.trim() });
        }
      } else {
        const data = await res.json();
        showToast(data.detail || t("audioPlaylists.saveError"), "error");
      }
    } catch {
      showToast(t("audioPlaylists.saveConnectionError"), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDragStart = (e: React.DragEvent, indexOrId: number, source: "sequencer" | "library") => {
    setDragSource(source);
    if (source === "sequencer") {
      setDraggedIndex(indexOrId);
    } else {
      setDraggedTrackId(indexOrId);
    }
    e.dataTransfer.setData("text/plain", indexOrId.toString());
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  const handleDragLeave = () => setDragOverIndex(null);

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
    } else if (dragSource === "library" && draggedTrackId !== null) {
      const track = tracks.find((tr) => tr.id === draggedTrackId);
      if (track) {
        setPlaylistItems((prev) => {
          const copy = [...prev];
          copy.splice(targetIndex, 0, { track, backgroundId: null });
          return copy;
        });
      }
    }
    resetDragState();
  };

  const handleDropOnEmptyZone = (e: React.DragEvent) => {
    e.preventDefault();
    if (dragSource === "library" && draggedTrackId !== null) {
      const track = tracks.find((tr) => tr.id === draggedTrackId);
      if (track) setPlaylistItems((prev) => [...prev, { track, backgroundId: null }]);
    }
    resetDragState();
  };

  const resetDragState = () => {
    setDraggedIndex(null);
    setDraggedTrackId(null);
    setDragSource(null);
    setDragOverIndex(null);
  };

  const toggleCourseExpanded = (courseId: number) => {
    setExpandedCourseIds((prev) => {
      const next = new Set(prev);
      if (next.has(courseId)) next.delete(courseId);
      else next.add(courseId);
      return next;
    });
  };

  const availablePrograms = React.useMemo(() => {
    const set = new Set<string>();
    for (const c of courses) if (c.program) set.add(c.program);
    return Array.from(set).sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));
  }, [courses]);

  const filteredPlaylists = playlists.filter((p) =>
    p.name.toLowerCase().includes(playlistSearch.toLowerCase())
  );

  const filteredTracks = tracks.filter((tr) => {
    const matchesSearch =
      tr.title.toLowerCase().includes(trackSearch.toLowerCase()) ||
      tr.course_title.toLowerCase().includes(trackSearch.toLowerCase());
    const matchesProgram = !trackProgramFilter || tr.course_program === trackProgramFilter;
    return matchesSearch && matchesProgram;
  });

  // Regroupement par cours (réf. mission "groupes comme des cours entiers") :
  // seuls les cours ayant au moins une piste après filtrage sont affichés,
  // dans l'ordre où ils apparaissent déjà côté serveur (titre du cours).
  const groupedCourses = React.useMemo(() => {
    const byId = new Map<number, AudioTrackSummary[]>();
    for (const tr of filteredTracks) {
      const list = byId.get(tr.course_id);
      if (list) list.push(tr);
      else byId.set(tr.course_id, [tr]);
    }
    return courses
      .filter((c) => byId.has(c.id))
      .map((c) => ({ course: c, tracks: byId.get(c.id)! }));
  }, [courses, filteredTracks]);

  const isSearching = trackSearch.trim().length > 0;

  const totalDurationSeconds = playlistItems.reduce((acc, item) => acc + (item.track.duration_seconds ?? 0), 0);

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
          <h3 style={{ fontSize: "1.1rem", margin: "0 0 16px", color: "var(--text-main)", fontWeight: 800 }}>
            {t("audioPlaylists.title")}
          </h3>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "16px" }}>
            <input
              type="text"
              className="form-control"
              placeholder={t("audioPlaylists.searchPlaceholder")}
              value={playlistSearch}
              onChange={(e) => setPlaylistSearch(e.target.value)}
              style={{ height: "38px", fontSize: "0.85rem" }}
            />
            <button className="btn btn-primary" onClick={handleCreateOpen} style={{ width: "100%", height: "38px" }}>
              <Icon name="add" size={18} />
              {t("audioPlaylists.createPlaylist")}
            </button>
          </div>

          <div className="playlists-scroll-area" style={isMobile ? { maxHeight: "260px" } : undefined}>
            {loading ? (
              <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)", fontSize: "0.9rem" }}>
                {t("audioPlaylists.loading")}
              </div>
            ) : filteredPlaylists.length === 0 ? (
              <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                {t("audioPlaylists.noPlaylistsFound")}
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
                        {t("audioPlaylists.coursesCount", { count: p.item_count })}
                      </span>
                      <span>{formatDuration(p.total_duration_seconds)}</span>
                    </div>
                    <div className="playlist-card-actions">
                      <button
                        className="btn btn-primary"
                        style={{ height: "28px", padding: "0 10px", fontSize: "0.75rem" }}
                        onClick={(e) => handleLaunch(e, p.id)}
                        title={t("audioPlaylists.launch")}
                      >
                        <Icon name="play_arrow" size={14} filled />
                        {t("audioPlaylists.launch")}
                      </button>
                      <button
                        className="btn btn-secondary"
                        style={{ height: "28px", padding: "0 8px", fontSize: "0.75rem" }}
                        onClick={(e) => handleDuplicate(e, p.id)}
                        title={t("audioPlaylists.duplicate")}
                      >
                        <Icon name="content_copy" size={14} />
                        {t("audioPlaylists.duplicate")}
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
              <Icon name="queue_music" size={48} color="var(--border-focus)" style={{ marginBottom: "12px" }} />
              <h4 style={{ margin: 0, fontWeight: 700, color: "var(--text-main)" }}>{t("audioPlaylists.editorTitle")}</h4>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
                {t("audioPlaylists.editorPlaceholderHint")}
              </p>
            </div>
          ) : (
            <form onSubmit={handleSave} className="playlist-editor-form" style={isMobile ? { height: "auto" } : undefined}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>
                  {isCreating ? t("audioPlaylists.newPlaylist") : t("audioPlaylists.editPlaylist")}
                </h3>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ height: "36px", padding: "0 16px", fontSize: "0.85rem" }}
                    disabled={isSaving}
                  >
                    {isSaving ? t("common.saving") : t("audioPlaylists.save")}
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
                  {t("audioPlaylists.nameLabel")}
                </label>
                <input
                  type="text"
                  className="form-control"
                  placeholder={t("audioPlaylists.namePlaceholder")}
                  value={playlistName}
                  onChange={(e) => setPlaylistName(e.target.value)}
                  required
                  disabled={isSaving}
                  style={{ height: "40px" }}
                />
              </div>

              <div className="editor-metadata-grid" style={isMobile ? { gridTemplateColumns: "1fr 1fr" } : undefined}>
                <div className="metadata-stat">
                  <span className="metadata-stat-label">{t("audioPlaylists.courseCountLabel")}</span>
                  <span className="metadata-stat-value">{playlistItems.length}</span>
                </div>
                <div className="metadata-stat">
                  <span className="metadata-stat-label">{t("audioPlaylists.totalDurationLabel")}</span>
                  <span className="metadata-stat-value">{formatDuration(totalDurationSeconds)}</span>
                </div>
                {!isMobile && (
                  <div className="metadata-stat">
                    <span className="metadata-stat-label">{t("audioPlaylists.statusLabel")}</span>
                    <span className="metadata-stat-value" style={{ color: "var(--accent-primary)", fontSize: "0.95rem", textTransform: "uppercase" }}>
                      {t("audioPlaylists.statusEditing")}
                    </span>
                  </div>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px", flex: "1 0 auto" }}>
                <span className="form-label" style={{ fontSize: "0.75rem", margin: 0 }}>
                  {t("audioPlaylists.sequencerLabel")}
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
                      <span>{t("audioPlaylists.emptySequencer")}</span>
                      <span style={{ fontSize: "0.75rem", opacity: 0.7 }}>{t("audioPlaylists.emptySequencerHint")}</span>
                    </div>
                  ) : (
                    playlistItems.map((item, index) => {
                      const isDragged = draggedIndex === index && dragSource === "sequencer";
                      const isOver = dragOverIndex === index;
                      return (
                        <div
                          key={`${item.track.id}-${index}`}
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
                              {item.track.title}
                            </div>
                            <div style={{ display: "flex", gap: "6px", alignItems: "center", marginTop: "1px" }}>
                              {item.track.course_program && (
                                <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                                  {item.track.course_program}
                                </span>
                              )}
                              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                                {item.track.course_title} · {formatTrackDuration(item.track.duration_seconds)}
                              </span>
                            </div>
                            <select
                              className="filter-select"
                              value={item.backgroundId ?? ""}
                              onChange={(e) => handleSetTrackBackground(index, e.target.value ? Number(e.target.value) : null)}
                              onClick={(e) => e.stopPropagation()}
                              title={t("audioPlaylists.trackBackgroundLabel")}
                              style={{ height: "22px", fontSize: "0.68rem", padding: "0 4px", marginTop: "3px", maxWidth: "180px" }}
                            >
                              <option value="">{t("audioPlaylists.trackBackgroundNone")}</option>
                              {backgrounds.map((bg) => (
                                <option key={bg.id} value={bg.id}>{bg.title}</option>
                              ))}
                            </select>
                          </div>
                          <div style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleMoveUp(index)}
                              disabled={index === 0}
                              title={t("audioPlaylists.moveUp")}
                            >
                              <Icon name="arrow_upward" size={14} />
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleMoveDown(index)}
                              disabled={index === playlistItems.length - 1}
                              title={t("audioPlaylists.moveDown")}
                            >
                              <Icon name="arrow_downward" size={14} />
                            </button>
                            <button
                              type="button"
                              className="btn btn-danger"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleRemoveTrack(index)}
                              title={t("audioPlaylists.remove")}
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

              {/* Ajout depuis les cours : cartes dépliables + "tout le cours"
                  (réf. mission "groupes comme des cours entiers" + "sans
                  image, à l'aveugle"). */}
              <div className="library-picker" style={{ height: isMobile ? "auto" : "340px", maxHeight: isMobile ? "380px" : undefined }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="form-label" style={{ fontSize: "0.75rem", margin: 0, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}>
                    {t("audioPlaylists.libraryPickerLabel")}
                  </span>
                </div>

                <div style={{ display: "flex", gap: "8px", flexWrap: isMobile ? "wrap" : "nowrap" }}>
                  <input
                    type="text"
                    className="form-control"
                    style={{ flex: 1, height: "32px", fontSize: "0.8rem", padding: "0 10px", minWidth: isMobile ? "100%" : undefined }}
                    placeholder={t("audioPlaylists.courseSearchPlaceholder")}
                    value={trackSearch}
                    onChange={(e) => setTrackSearch(e.target.value)}
                  />
                  <select
                    className="filter-select"
                    style={{ height: "32px", fontSize: "0.8rem", padding: "0 8px" }}
                    value={trackProgramFilter}
                    onChange={(e) => setTrackProgramFilter(e.target.value)}
                  >
                    <option value="">{t("audioPlaylists.allProgramsShort")}</option>
                    {availablePrograms.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>

                <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px", paddingRight: "2px" }}>
                  {groupedCourses.length === 0 ? (
                    <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem", padding: "16px" }}>
                      {t("audioPlaylists.noMatchingCourses")}
                    </div>
                  ) : (
                    groupedCourses.map(({ course, tracks: courseTracks }) => {
                      const thumbSrc = getCourseThumbSrc(course);
                      const expanded = isSearching || expandedCourseIds.has(course.id);
                      return (
                        <div key={course.id} className="picker-course-card">
                          <div className="picker-course-header" onClick={() => toggleCourseExpanded(course.id)}>
                            <div className="picker-course-thumb">
                              {thumbSrc ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={thumbSrc} alt="" />
                              ) : (
                                <Icon name="library_music" size={18} style={{ opacity: 0.3 }} />
                              )}
                            </div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {course.title}
                              </div>
                              <div style={{ display: "flex", gap: "6px", alignItems: "center", marginTop: "1px" }}>
                                {course.program && (
                                  <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                                    {course.program}
                                  </span>
                                )}
                                <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
                                  {t("audioPlaylists.tracksInCourse", { count: courseTracks.length })}
                                </span>
                              </div>
                            </div>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ height: "26px", padding: "0 8px", fontSize: "0.7rem", fontWeight: 700, flexShrink: 0 }}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleAddWholeCourse(course.id);
                              }}
                              title={t("audioPlaylists.addWholeCourse")}
                            >
                              <Icon name="playlist_add" size={14} />
                              {t("audioPlaylists.addWholeCourse")}
                            </button>
                            <Icon name={expanded ? "expand_less" : "expand_more"} size={18} color="var(--text-muted)" />
                          </div>

                          {expanded && (
                            <div className="picker-course-tracks">
                              {courseTracks.map((track) => (
                                <div
                                  key={track.id}
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
                                    {formatTrackDuration(track.duration_seconds)}
                                  </span>
                                  <button
                                    type="button"
                                    className="btn btn-secondary"
                                    style={{ height: "22px", padding: "0 6px", fontSize: "0.68rem", fontWeight: 700, flexShrink: 0 }}
                                    onClick={() => handleAddTrack(track)}
                                  >
                                    {t("audioPlaylists.addShort")}
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
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
            <h3 style={{ fontSize: "1.1rem", margin: "0 0 12px" }}>{t("audioPlaylists.deletePlaylistTitle")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: "0 0 20px", lineHeight: 1.5 }}>
              {t("audioPlaylists.deletePlaylistConfirmBefore")} <strong style={{ color: "var(--text-main)" }}>{playlistToDelete.name}</strong>{t("audioPlaylists.deletePlaylistConfirmAfter")}
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
