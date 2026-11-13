"use client";
import { errorMessage } from "@/lib/apiError";

import React, { useCallback, useEffect, useState } from "react";
import { usePlaylistSequencer } from "@/lib/usePlaylistSequencer";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useIsMobile } from "@/lib/useIsMobile";
import Icon from "@/components/Icon";
import AudioSequencer from "./playlist/AudioSequencer";
import AudioTrackPicker from "./playlist/AudioTrackPicker";
import PlaylistList from "@/components/PlaylistList";
import type { AudioPlaylistDetail, AudioPlaylistItemInput, AudioPlaylistSummary, AudioTrackSummary, AudioCourseSummary, BackgroundSummary, PlaylistDraftItem } from "./playlist/types";
import { getApiUrl } from "@/lib/apiUrl";
import { formatMinutes } from "@/lib/format";
import { useToast } from "@/lib/useToast";

export default function AudioPlaylistManager() {
  const { t } = useAppSettings();
  const isMobile = useIsMobile();
  const { connected, sendCommand } = usePlaybackSocket();
  const [playlists, setPlaylists] = useState<AudioPlaylistSummary[]>([]);
  const [tracks, setTracks] = useState<AudioTrackSummary[]>([]);
  const [courses, setCourses] = useState<AudioCourseSummary[]>([]);
  const [backgrounds, setBackgrounds] = useState<BackgroundSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const { toast, showToast } = useToast();

  const [selectedPlaylistId, setSelectedPlaylistId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [playlistName, setPlaylistName] = useState<string>("");
  const [playlistItems, setPlaylistItems] = useState<PlaylistDraftItem[]>([]);

  const sequencer = usePlaylistSequencer<PlaylistDraftItem>(setPlaylistItems, (id) => {
    const track = tracks.find((tr) => tr.id === id);
    return track ? { track, backgroundId: null } : undefined;
  });
  const [isSaving, setIsSaving] = useState<boolean>(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [playlistToDelete, setPlaylistToDelete] = useState<AudioPlaylistSummary | null>(null);

  const fetchPlaylists = useCallback(() => fetch(getApiUrl("/audio-playlists"), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setPlaylists(await res.json());
      else showToast(t("audioPlaylists.fetchError"), "error");
    })
    .catch(() => showToast(t("audioPlaylists.fetchNetworkError"), "error")), [showToast, t]);

  const fetchTracks = useCallback(() => fetch(getApiUrl("/audio/tracks"), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setTracks(await res.json());
    })
    .catch(() => showToast(t("audioPlaylists.coursesNetworkError"), "error")), [showToast, t]);

  useEffect(() => {
    const quiet = <T,>(path: string, apply: (data: T) => void) => fetch(getApiUrl(path), { cache: "no-store" })
      .then(async (res) => {
        if (res.ok) apply(await res.json());
      })
      .catch(() => {});
    Promise.all([fetchPlaylists(), fetchTracks(), quiet("/audio", setCourses), quiet("/backgrounds", setBackgrounds)])
      .finally(() => setLoading(false));
  }, [fetchPlaylists, fetchTracks]);

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
  };

  const handleSelectPlaylist = async (summary: AudioPlaylistSummary) => {
    setSelectedPlaylistId(summary.id);
    setIsCreating(false);
    setPlaylistName(summary.name);
    setPlaylistItems([]);

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

  const handleAddWholeCourse = (courseId: number) => {
    const courseTracks = tracks.filter((tr) => tr.course_id === courseId);
    if (courseTracks.length === 0) return;
    setPlaylistItems((prev) => [...prev, ...courseTracks.map((track) => ({ track, backgroundId: null }))]);
    const course = courses.find((c) => c.id === courseId);
    showToast(t("audioPlaylists.addedWholeCourseToast", { title: course?.title ?? "", count: courseTracks.length }));
  };

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
        showToast(errorMessage(data, t("audioPlaylists.saveError")), "error");
      }
    } catch {
      showToast(t("audioPlaylists.saveConnectionError"), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const totalDurationSeconds = playlistItems.reduce((acc, item) => acc + (item.track.duration_seconds ?? 0), 0);

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
          prefix="audioPlaylists" t={t} isMobile={isMobile} loading={loading} playlists={playlists}
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
                  <span className="metadata-stat-value">{formatMinutes(totalDurationSeconds, "0 min")}</span>
                </div>
                {!isMobile && (
                  <div className="metadata-stat">
                    <span className="metadata-stat-label">{t("audioPlaylists.statusLabel")}</span>
                    <span className="metadata-stat-value" style={{ color: "var(--accent-text)", fontSize: "0.95rem", textTransform: "uppercase" }}>
                      {t("audioPlaylists.statusEditing")}
                    </span>
                  </div>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px", flex: "1 0 auto" }}>
                <span className="form-label" style={{ fontSize: "0.75rem", margin: 0 }}>
                  {t("audioPlaylists.sequencerLabel")}
                </span>

                <AudioSequencer
                  t={t} isMobile={isMobile} playlistItems={playlistItems} backgrounds={backgrounds}
                  sequencer={sequencer} handleSetTrackBackground={handleSetTrackBackground}
                />
              </div>

              <AudioTrackPicker
                key={selectedPlaylistId ?? "new"}
                t={t} isMobile={isMobile} tracks={tracks} courses={courses} sequencer={sequencer}
                handleAddTrack={handleAddTrack} handleAddWholeCourse={handleAddWholeCourse}
              />
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
