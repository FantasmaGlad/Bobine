"use client";

import React, { useEffect, useState } from "react";

import Icon from "@/components/Icon";
import Toast from "@/components/Toast";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast, ToastState } from "@/lib/useToast";

import { appendToPlaylist, deleteVideos } from "./bulk";
import { AddToPlaylistDialog, BulkDeleteDialog, DeleteVideoDialog } from "./LibraryDialogs";
import LibraryToolbar, { type LibraryFilters } from "./LibraryToolbar";
import SelectionBar from "./SelectionBar";
import { useSelection } from "./selection";
import { PROGRAMS_LIST_ID, type Video } from "./types";
import UploadZone from "./UploadZone";
import { useLibraryData } from "./useLibraryData";
import type { useLibraryUploads } from "./useLibraryUploads";
import VideoGrid from "./VideoGrid";
import VideoStudio from "./VideoStudio";
import VideoTable from "./VideoTable";

interface Props {
  uploads: ReturnType<typeof useLibraryUploads>;
  onPick: () => void;
  toast: ToastState | null;
  showToast: ShowToast;
  programsRef: React.MutableRefObject<string[]>;
}

const CENTERED = { display: "flex", flex: 1, alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" } as const;

function EmptyLibrary() {
  const { t } = useAppSettings();
  return (
    <div style={{ ...CENTERED, flexDirection: "column" }}>
      <Icon name="video_library" size={48} color="var(--border-focus)" style={{ marginBottom: "12px" }} />
      <p style={{ margin: 0, fontWeight: 600 }}>{t("library.noVideosFound")}</p>
      <p style={{ fontSize: "0.85rem", margin: "4px 0 0" }}>{t("library.noVideosHint")}</p>
    </div>
  );
}

export default function LibraryMedia({ uploads, onPick, toast, showToast, programsRef }: Props) {
  const { t } = useAppSettings();
  const [filters, setFilters] = useState<LibraryFilters>({ search: "", program: "", release: "", sortBy: "imported_at" });
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [selected, setSelected] = useState<Video | null>(null);
  const [toDelete, setToDelete] = useState<Video | null>(null);
  const [bulkDelete, setBulkDelete] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [target, setTarget] = useState("");
  const data = useLibraryData(filters, showToast);
  const selection = useSelection(data.videos);
  useEffect(() => {
    programsRef.current = data.availablePrograms;
  }, [programsRef, data.availablePrograms]);

  const replaceVideo = (video: Video) => {
    data.setVideos((prev) => prev.map((v) => (v.id === video.id ? video : v)));
    setSelected(video);
    data.fetchPrograms();
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      const res = await fetch(getApiUrl(`/videos/${toDelete.id}`), { method: "DELETE" });
      if (!res.ok) {
        showToast(t("library.deleteError"), "error");
        return;
      }
      showToast(t("library.deletedSuccess"));
      data.setVideos((prev) => prev.filter((v) => v.id !== toDelete.id));
      if (selected?.id === toDelete.id) setSelected(null);
    } catch {
      showToast(t("library.deleteGenericError"), "error");
    } finally {
      setToDelete(null);
    }
  };

  const confirmBulkDelete = async () => {
    const ids = Array.from(selection.selectedIds);
    const failed = await deleteVideos(ids);
    showToast(
      failed > 0 ? t("library.bulkDeletedPartial", { ok: ids.length - failed, total: ids.length }) : t("library.bulkDeletedAll", { count: ids.length }),
      failed > 0 ? "warning" : "success"
    );
    setBulkDelete(false);
    selection.clear();
    data.fetchVideos();
  };

  const closeAdd = () => {
    setAddOpen(false);
    setTarget("");
  };

  const confirmAdd = async () => {
    if (!target) return;
    try {
      const name = await appendToPlaylist(target, Array.from(selection.selectedIds));
      showToast(t("library.addedToPlaylist", { count: selection.selectedIds.size, name }));
      closeAdd();
      selection.clear();
    } catch {
      showToast(t("library.addToPlaylistError"), "error");
    }
  };

  const content = data.loading ? (
    <div style={CENTERED}>{t("library.loadingLibrary")}</div>
  ) : data.videos.length === 0 ? (
    <EmptyLibrary />
  ) : viewMode === "grid" ? (
    <VideoGrid videos={data.videos} selection={selection} onOpen={setSelected} />
  ) : (
    <VideoTable videos={data.videos} selection={selection} onOpen={setSelected} />
  );

  return (
    <>
      <datalist id={PROGRAMS_LIST_ID}>
        {data.availablePrograms.map((p) => <option key={p} value={p} />)}
      </datalist>
      <Toast toast={toast} />
      {(uploads.dragActive || uploads.specs.length > 0) && (
        <UploadZone
          dragActive={uploads.dragActive}
          specs={uploads.specs}
          onDrag={uploads.onDrag}
          onDrop={uploads.onDrop}
          onPick={onPick}
          onUpdate={uploads.update}
          onRemove={uploads.remove}
          onSubmit={uploads.submit}
          onClear={uploads.clear}
        />
      )}
      {selection.selectedIds.size > 0 && (
        <SelectionBar count={selection.selectedIds.size} onAddToPlaylist={() => setAddOpen(true)} onDelete={() => setBulkDelete(true)} onClear={selection.clear} />
      )}
      <LibraryToolbar
        filters={filters}
        onChange={(patch) => setFilters((prev) => ({ ...prev, ...patch }))}
        programs={data.availablePrograms}
        suggestions={data.suggestions}
        viewMode={viewMode}
        onViewMode={setViewMode}
      />
      {content}
      {selected && (
        <VideoStudio key={selected.id} video={selected} showToast={showToast} onClose={() => setSelected(null)} onUpdated={replaceVideo} onDelete={setToDelete} />
      )}
      {toDelete && <DeleteVideoDialog video={toDelete} onConfirm={confirmDelete} onCancel={() => setToDelete(null)} />}
      {bulkDelete && <BulkDeleteDialog count={selection.selectedIds.size} onConfirm={confirmBulkDelete} onCancel={() => setBulkDelete(false)} />}
      {addOpen && (
        <AddToPlaylistDialog count={selection.selectedIds.size} playlists={data.playlists} target={target} onTarget={setTarget} onConfirm={confirmAdd} onCancel={closeAdd} />
      )}
    </>
  );
}
