"use client";

import { useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

import { fetchJson, sendJson } from "./api";
import type { PlaylistDetail, RadioTrack } from "./types";

export function useTrackSelection(tracks: RadioTrack[], showToast: ShowToast, refreshAll: () => void) {
  const { t } = useAppSettings();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [menu, setMenu] = useState<null | "tag" | "playlist">(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const clear = () => {
    setSelected(new Set());
    setMenu(null);
  };

  const toggleAll = (ids: number[]) => {
    const all = ids.length > 0 && ids.every((id) => selected.has(id));
    setSelected((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (all ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const targets = () => tracks.filter((tr) => selected.has(tr.id));

  const tagState = (name: string): "all" | "some" | "none" => {
    const chosen = targets();
    const withTag = chosen.filter((tr) => tr.tags.includes(name)).length;
    if (chosen.length === 0 || withTag === 0) return "none";
    return withTag === chosen.length ? "all" : "some";
  };

  const applyTag = async (name: string, add: boolean) => {
    await Promise.all(targets().map((tr) => {
      if (add === tr.tags.includes(name)) return Promise.resolve();
      const tags = add ? [...tr.tags, name] : tr.tags.filter((x) => x !== name);
      return sendJson(`/radio/tracks/${tr.id}`, "PUT", { tags });
    }));
    showToast(t("radioLibrary.tagsAppliedToast"));
    refreshAll();
  };

  const addToPlaylist = async (playlistId: number) => {
    const detail = await fetchJson<PlaylistDetail | null>(`/radio/playlists/${playlistId}`, null);
    if (!detail) {
      showToast(t("radioLibrary.playlistError"), "error");
      return;
    }
    const merged = detail.items.map((i) => i.track.id);
    selected.forEach((id) => {
      if (!merged.includes(id)) merged.push(id);
    });
    try {
      const res = await sendJson(`/radio/playlists/${playlistId}`, "PUT", { name: detail.name, track_ids: merged });
      if (!res.ok) throw new Error();
      showToast(t("radioLibrary.bulkAddedToPlaylistToast"));
      setMenu(null);
      refreshAll();
    } catch {
      showToast(t("radioLibrary.playlistError"), "error");
    }
  };

  const remove = async () => {
    const ids = Array.from(selected);
    const responses = await Promise.all(ids.map((id) => fetch(getApiUrl(`/radio/tracks/${id}`), { method: "DELETE" }).catch(() => null)));
    const deleted = responses.filter((res) => res?.ok).length;
    if (deleted === 0) showToast(t("radioLibrary.deleteError"), "error");
    else showToast(t("radioLibrary.bulkDeletedToast", { count: deleted }), deleted < ids.length ? "error" : "success");
    setConfirmDelete(false);
    clear();
    refreshAll();
  };

  return { selected, menu, setMenu, confirmDelete, setConfirmDelete, toggle, clear, toggleAll, tagState, applyTag, addToPlaylist, remove };
}

export type TrackSelection = ReturnType<typeof useTrackSelection>;
