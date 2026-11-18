"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";

import { getApiUrl } from "@/lib/apiUrl";
import { useUploadManager } from "@/lib/UploadManager";

import { fetchJson } from "./api";
import type { AlbumEntry, ArtistEntry, PlaylistSummary, RadioTrack, TagEntry } from "./types";

const isRadioUpload = (kind: string) => kind === "radio_files" || kind === "radio_zip";

export function useRadioCatalog() {
  const [tracks, setTracks] = useState<RadioTrack[]>([]);
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [artists, setArtists] = useState<ArtistEntry[]>([]);
  const [albums, setAlbums] = useState<AlbumEntry[]>([]);
  const [tags, setTags] = useState<TagEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [coverVersion, setCoverVersion] = useState(0);
  const { uploads } = useUploadManager();
  const seenDoneIds = useRef<Set<string>>(new Set());

  const fetchAll = () => Promise.all([
    fetchJson<RadioTrack[]>("/radio/tracks", []),
    fetchJson<PlaylistSummary[]>("/radio/playlists", []),
    fetchJson<ArtistEntry[]>("/radio/artists", []),
    fetchJson<AlbumEntry[]>("/radio/albums", []),
    fetchJson<TagEntry[]>("/radio/tags", []),
  ]).then(([tr, pl, ar, al, tg]) => {
    setTracks(tr);
    setPlaylists(pl);
    setArtists(ar);
    setAlbums(al);
    setTags(tg);
    setLoading(false);
  });

  const refreshAll = () => {
    setLoading(true);
    return fetchAll();
  };

  const reloadCatalog = useEffectEvent(() => fetchAll());

  const refreshPlaylists = async () => setPlaylists(await fetchJson<PlaylistSummary[]>("/radio/playlists", []));

  useEffect(() => {
    reloadCatalog();
  }, []);

  useEffect(() => {
    const newlyDone = uploads.filter((u) => isRadioUpload(u.kind) && u.status === "done" && !seenDoneIds.current.has(u.id));
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    void reloadCatalog();
  }, [uploads]);

  const coverUrl = (id: number) => `${getApiUrl(`/radio/tracks/${id}/cover`)}?v=${coverVersion}`;
  const bumpCovers = () => setCoverVersion((v) => v + 1);

  return { tracks, playlists, artists, albums, tags, loading, refreshAll, refreshPlaylists, coverUrl, bumpCovers };
}

export type RadioCatalog = ReturnType<typeof useRadioCatalog>;
