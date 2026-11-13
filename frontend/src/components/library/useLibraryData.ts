"use client";

import React, { useEffect, useRef, useState } from "react";

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

  const fetchVideos = async () => {
    await Promise.resolve();
    if (recallCatalog<Video>(CACHE_KEY) === undefined) setLoading(true);
    try {
      const res = await fetch(getApiUrl(`/videos?${videosQuery(filters)}`), { cache: "no-store" });
      if (!res.ok) {
        showToast(t("library.fetchError"), "error");
        return;
      }
      const data = await res.json();
      setVideos(data);
      if (!filters.search && !filters.program && !filters.release) rememberCatalog(CACHE_KEY, data as Video[]);
    } catch {
      showToast(t("library.connectionError"), "error");
    } finally {
      setLoading(false);
    }
  };

  const fetchPrograms = () => {
    fetch(getApiUrl("/videos/programs"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then((data: string[]) => setPrograms(Array.isArray(data) ? data : []))
      .catch(() => {});
  };

  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => (u.kind === "video" || u.kind === "video_zip") && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    fetchVideos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploads]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchVideos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.search, filters.program, filters.release, filters.sortBy]);

  useEffect(() => {
    fetch(getApiUrl("/playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setPlaylists)
      .catch(() => setPlaylists([]));
  }, []);

  useEffect(fetchPrograms, []);

  useEffect(() => {
    if (libraryVersion === 0) return;
    fetchVideos();
    fetchPrograms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [libraryVersion]);

  const suggestions = React.useMemo(() => videos.flatMap((v) => (v.program ? [v.title, v.program] : [v.title])), [videos]);
  const availablePrograms = React.useMemo(() => sortedPrograms(programs, videos), [programs, videos]);

  return { videos, setVideos, loading, playlists, suggestions, availablePrograms, fetchVideos, fetchPrograms };
}
