import { useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import type { PlaylistEditorConfig, PlaylistSummary } from "./types";

export function usePlaylistDraft<Item, Detail>(config: PlaylistEditorConfig<Item, Detail>) {
  const { endpoint, prefix, itemsFrom, t, showToast } = config;
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [playlistName, setPlaylistName] = useState("");
  const [playlistItems, setPlaylistItems] = useState<Item[]>([]);

  const reset = (creating: boolean) => {
    setSelectedPlaylistId(null);
    setIsCreating(creating);
    setPlaylistName("");
    setPlaylistItems([]);
  };

  const select = async (summary: PlaylistSummary) => {
    setSelectedPlaylistId(summary.id);
    setIsCreating(false);
    setPlaylistName(summary.name);
    setPlaylistItems([]);
    try {
      const res = await fetch(getApiUrl(`${endpoint}/${summary.id}`), { cache: "no-store" });
      if (res.ok) setPlaylistItems(itemsFrom(await res.json()));
      else showToast(t(`${prefix}.detailFetchError`), "error");
    } catch {
      showToast(t(`${prefix}.networkError`), "error");
    }
  };

  return {
    selectedPlaylistId, isCreating, playlistName, setPlaylistName, playlistItems, setPlaylistItems,
    select, openCreate: () => reset(true), cancel: () => reset(false),
  };
}

export type PlaylistDraft<Item> = ReturnType<typeof usePlaylistDraft<Item, unknown>>;

