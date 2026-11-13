"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { recallCatalog, rememberCatalog } from "@/lib/sessionCatalog";
import { useUploadManager } from "@/lib/UploadManager";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import type { ShowToast } from "@/lib/useToast";

import type { LibraryFilters } from "./LibraryToolbar";
import type { Video } from "./types";

const CACHE_KEY = "library.videos";

function videosQuery(filters: LibraryFilters): string {
  const query = new URLSearchParams();
  if (filters.search) query.append("search", filters.search);
  if (filters.program) query.append("program", filters.program);
  if (filters.release) query.append("release", filters.release);
  query.append("sort_by", filters.sortBy);
  query.append("order", "desc");
  return query.toString();
}

function sortedPrograms(programs: string[], videos: Video[]): string[] {
  const set = new Set<string>(programs);
  for (const v of videos) if (v.program) set.add(v.program);
  return Array.from(set).sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));
}

export function useLibraryData(filters: LibraryFilters, showToast: ShowToast) {
  const { t } = useAppSettings();
  const [videos, setVideos] = useState<Video[]>(() => recallCatalog<Video>(CACHE_KEY) ?? []);
  const [loading, setLoading] = useState<boolean>(() => recallCatalog<Video>(CACHE_KEY) === undefined);
  const [programs, setPrograms] = useState<string[]>([]);
  const [playlists, setPlaylists] = useState<{ id: number; name: string }[]>([]);
  const { uploads } = useUploadManager();
  const { libraryVersion } = usePlaybackSocket();
  const seenDoneIds = useRef<Set<string>>(new Set());

  const query = videosQuery(filters);
  const cacheable = !filters.search && !filters.program && !filters.release;

  const fetchVideos = useCallback(() => Promise.resolve()
    .then(() => {
      if (recallCatalog<Video>(CACHE_KEY) === undefined) setLoading(true);
      return fetch(getApiUrl(`/videos?${query}`), { cache: "no-store" });
    })
    .then(async (res) => {
      if (!res.ok) {
        showToast(t("library.fetchError"), "error");
        return;
      }
      const data = await res.json();
      setVideos(data);
      if (cacheable) rememberCatalog(CACHE_KEY, data as Video[]);
    })
    .catch(() => showToast(t("library.connectionError"), "error"))
    .finally(() => setLoading(false)), [query, cacheable, showToast, t]);

  const fetchPrograms = useCallback(() => fetch(getApiUrl("/videos/programs"), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : []))
    .then((data: string[]) => setPrograms(Array.isArray(data) ? data : []))
    .catch(() => {}), []);

  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => (u.kind === "video" || u.kind === "video_zip") && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    void fetchVideos();
  }, [uploads, fetchVideos]);

  useEffect(() => {
    void fetchVideos();
  }, [fetchVideos]);

  useEffect(() => {
    fetch(getApiUrl("/playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setPlaylists)
      .catch(() => setPlaylists([]));
  }, []);

  useEffect(() => {
    void fetchPrograms();
  }, [fetchPrograms]);

  const reload = useRef(() => {});
  useEffect(() => {
    reload.current = () => {
      void fetchVideos();
      void fetchPrograms();
    };
  }, [fetchVideos, fetchPrograms]);
  useEffect(() => {
    if (libraryVersion !== 0) reload.current();
  }, [libraryVersion]);

  const suggestions = React.useMemo(() => videos.flatMap((v) => (v.program ? [v.title, v.program] : [v.title])), [videos]);
  const availablePrograms = React.useMemo(() => sortedPrograms(programs, videos), [programs, videos]);

  return { videos, setVideos, loading, playlists, suggestions, availablePrograms, fetchVideos, fetchPrograms };
}
