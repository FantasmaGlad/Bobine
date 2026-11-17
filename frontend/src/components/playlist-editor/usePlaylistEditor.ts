import { useCallback, useState } from "react";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { PlaylistEditorConfig, PlaylistSummary } from "./types";
import { usePlaylistDraft, type PlaylistDraft } from "./usePlaylistDraft";

function usePlaylistList<Item, Detail>({ endpoint, prefix, t, showToast }: PlaylistEditorConfig<Item, Detail>) {
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const fetchPlaylists = useCallback(() => fetch(getApiUrl(endpoint), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setPlaylists(await res.json());
      else showToast(t(`${prefix}.fetchError`), "error");
    })
    .catch(() => showToast(t(`${prefix}.fetchNetworkError`), "error")), [endpoint, prefix, showToast, t]);
  return { playlists, setPlaylists, fetchPlaylists };
}

async function reselectAfterSave<Item>(endpoint: string, name: string, draft: PlaylistDraft<Item>, playlists: PlaylistSummary[]) {
  if (draft.selectedPlaylistId) {
    const activeSummary = playlists.find((p) => p.id === draft.selectedPlaylistId);
    if (activeSummary) draft.select({ ...activeSummary, name });
    return;
  }
  const res = await fetch(getApiUrl(endpoint), { cache: "no-store" });
  const created = res.ok ? (await res.json() as PlaylistSummary[]).find((p) => p.name === name) : undefined;
  if (created) draft.select(created);
  else draft.cancel();
}

export function usePlaylistEditor<Item, Detail>(config: PlaylistEditorConfig<Item, Detail>) {
  const { endpoint, prefix, payload, t, showToast } = config;
  const list = usePlaylistList(config);
  const draft = usePlaylistDraft(config);
  const [isSaving, setIsSaving] = useState(false);
  const [playlistToDelete, setPlaylistToDelete] = useState<PlaylistSummary | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = draft.playlistName.trim();
    if (!name) {
      showToast(t(`${prefix}.emptyNameWarning`), "warning");
      return;
    }
    setIsSaving(true);
    try {
      const id = draft.selectedPlaylistId;
      const res = await fetch(getApiUrl(id ? `${endpoint}/${id}` : endpoint), {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, items: payload(draft.playlistItems) }),
      });
      if (!res.ok) {
        showToast(errorMessage(await res.json(), t(`${prefix}.saveError`)), "error");
        return;
      }
      showToast(id ? t(`${prefix}.updatedToast`) : t(`${prefix}.createdToast`));
      list.fetchPlaylists();
      await reselectAfterSave(endpoint, name, draft as PlaylistDraft<Item>, list.playlists);
    } catch {
      showToast(t(`${prefix}.saveConnectionError`), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const duplicate = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      const res = await fetch(getApiUrl(`${endpoint}/${id}/duplicate`), { method: "POST" });
      if (res.ok) {
        showToast(t(`${prefix}.duplicatedToast`));
        list.fetchPlaylists();
      } else {
        showToast(t(`${prefix}.duplicateError`), "error");
      }
    } catch {
      showToast(t(`${prefix}.connectionError`), "error");
    }
  };

  const confirmDelete = async () => {
    const target = playlistToDelete;
    if (!target) return;
    try {
      const res = await fetch(getApiUrl(`${endpoint}/${target.id}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t(`${prefix}.deletedToast`));
        list.setPlaylists((prev) => prev.filter((p) => p.id !== target.id));
        if (draft.selectedPlaylistId === target.id) draft.cancel();
      } else {
        showToast(t(`${prefix}.deleteError`), "error");
      }
    } catch {
      showToast(t(`${prefix}.deleteNetworkError`), "error");
    } finally {
      setPlaylistToDelete(null);
    }
  };

  const askDelete = (e: React.MouseEvent, playlist: PlaylistSummary) => {
    e.stopPropagation();
    setPlaylistToDelete(playlist);
  };

  return {
    ...list, draft, isSaving, save, duplicate, playlistToDelete, askDelete, confirmDelete,
    cancelDelete: () => setPlaylistToDelete(null),
  };
}

export type PlaylistEditor<Item> = ReturnType<typeof usePlaylistEditor<Item, unknown>>;
