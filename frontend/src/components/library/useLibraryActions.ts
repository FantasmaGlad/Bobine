"use client";

import { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import { appendToPlaylist, deleteVideos } from "./bulk";
import type { useSelection } from "./selection";
import type { Video } from "./types";
import type { useLibraryData } from "./useLibraryData";

type Data = ReturnType<typeof useLibraryData>;
type Selection = ReturnType<typeof useSelection>;

export function useLibraryActions(data: Data, selection: Selection, showToast: ShowToast, selected: Video | null, setSelected: (video: Video | null) => void) {
  const { t } = useAppSettings();
  const [toDelete, setToDelete] = useState<Video | null>(null);
  const [bulkDelete, setBulkDelete] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [target, setTarget] = useState("");

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

  return { toDelete, setToDelete, bulkDelete, setBulkDelete, addOpen, setAddOpen, target, setTarget, confirmDelete, confirmBulkDelete, closeAdd, confirmAdd };
}
