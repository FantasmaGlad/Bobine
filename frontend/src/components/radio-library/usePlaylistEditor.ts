"use client";

import { useEffect, useRef, useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import type { ShowToast } from "@/lib/useToast";

import { fetchJson, sendJson } from "./api";
import type { OutputDefaults, PlaylistDetail, PlaylistSummary, RadioOutput } from "./types";
import type { RadioCatalog } from "./useRadioCatalog";

export function usePlaylistEditor(catalog: RadioCatalog, showToast: ShowToast) {
  const { t } = useAppSettings();
  const [playlist, setPlaylist] = useState<PlaylistDetail | null>(null);
  const [addingTrackId, setAddingTrackId] = useState<number | null>(null);
  const [toDelete, setToDelete] = useState<PlaylistSummary | null>(null);
  const [outputDefaults, setOutputDefaults] = useState<OutputDefaults | null>(null);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const current = useRef<PlaylistDetail | null>(null);
  const savedName = useRef("");
  const fail = () => showToast(t("radioLibrary.playlistError"), "error");

  useEffect(() => {
    current.current = playlist;
  }, [playlist]);

  useEffect(() => {
    fetchJson<OutputDefaults | null>("/radio/default-playlist", null).then((data) => data && setOutputDefaults(data));
  }, []);

  const serial = (fn: () => Promise<void>) => {
    const run = queue.current.then(fn, fn);
    queue.current = run.catch(() => undefined);
    return run;
  };

  const accept = (detail: PlaylistDetail) => {
    savedName.current = detail.name;
    setPlaylist(detail);
  };

  const adopt = async (res: Response) => {
    if (!res.ok) return fail();
    accept(await res.json());
    catalog.refreshPlaylists();
  };

  const request = async (path: string, method: string, body?: unknown) => {
    try {
      await adopt(await sendJson(path, method, body));
    } catch {
      fail();
    }
  };

  const save = (id: number, name: string, trackIds: number[]) => request(`/radio/playlists/${id}`, "PUT", { name, track_ids: trackIds });

  const withCurrent = (fn: (p: PlaylistDetail) => Promise<void>) => serial(async () => {
    if (current.current) await fn(current.current);
  });

  const open = async (id: number) => {
    const detail = await fetchJson<PlaylistDetail | null>(`/radio/playlists/${id}`, null);
    if (detail) accept(detail);
    else fail();
  };

  const create = async (name: string): Promise<boolean> => {
    try {
      const res = await sendJson("/radio/playlists", "POST", { name, track_ids: [] });
      if (!res.ok) throw new Error();
      showToast(t("radioLibrary.playlistCreatedToast"));
      accept(await res.json());
      catalog.refreshPlaylists();
      return true;
    } catch {
      fail();
      return false;
    }
  };

  const ids = (p: PlaylistDetail) => p.items.map((i) => i.track.id);

  const rename = (name: string) => withCurrent((p) => (savedName.current === name ? Promise.resolve() : save(p.id, name, ids(p))));
  const removeTrack = (trackId: number) => withCurrent((p) => save(p.id, p.name, ids(p).filter((id) => id !== trackId)));

  const move = (from: number, to: number) => withCurrent((p) => {
    const order = ids(p);
    const [moved] = order.splice(from, 1);
    order.splice(to, 0, moved);
    return save(p.id, p.name, order);
  });

  const addTrack = (trackId: number) => {
    const p = current.current;
    if (!p) return;
    setAddingTrackId(trackId);
    serial(async () => {
      await request(`/radio/playlists/${p.id}/tracks`, "POST", { track_id: trackId });
      setAddingTrackId((id) => (id === trackId ? null : id));
    });
  };

  const toggleDefault = () => withCurrent((p) => request(`/radio/playlists/${p.id}/default`, p.is_default ? "DELETE" : "PUT"));

  const toggleOutput = async (output: RadioOutput) => {
    const p = current.current;
    if (!p) return;
    const chosen = outputDefaults?.[output]?.override_playlist_id === p.id;
    try {
      const res = await sendJson("/radio/default-playlist", "PUT", { channel: output, playlist_id: chosen ? null : p.id });
      if (res.ok) setOutputDefaults(await res.json());
      else fail();
    } catch {
      fail();
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    try {
      const res = await sendJson(`/radio/playlists/${toDelete.id}`, "DELETE");
      if (!res.ok) return fail();
      showToast(t("radioLibrary.playlistDeletedToast"));
      if (playlist?.id === toDelete.id) setPlaylist(null);
      catalog.refreshAll();
    } catch {
      fail();
    } finally {
      setToDelete(null);
    }
  };

  return {
    playlist, setPlaylist, close: () => setPlaylist(null), addingTrackId, outputDefaults, toDelete, setToDelete,
    open, create, rename, removeTrack, move, addTrack, toggleDefault, toggleOutput, remove,
  };
}

export type PlaylistEditor = ReturnType<typeof usePlaylistEditor>;
