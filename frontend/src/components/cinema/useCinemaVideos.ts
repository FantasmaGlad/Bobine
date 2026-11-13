"use client";

import { useEffect, useMemo, useState } from "react";

import { getApiUrl } from "@/lib/apiUrl";
import type { CinemaVideo } from "@/lib/cinemaCatalog";

const SCRAMBLE_INTERVAL_MS = 15 * 60 * 1000;
const FIELDS = ["id", "title", "program", "release", "duration_seconds", "thumbnail_path"] as const;

const sameList = (a: CinemaVideo[], b: CinemaVideo[]) =>
  a.length === b.length && a.every((v, i) => b[i] && FIELDS.every((field) => v[field] === b[i][field]));

export function useCinemaVideos(libraryVersion: number) {
  const [videos, setVideos] = useState<CinemaVideo[]>([]);
  useEffect(() => {
    let cancelled = false;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const load = () => {
      fetch(getApiUrl("/videos?sort_by=title&order=asc"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
        .then((data: CinemaVideo[]) => {
          if (!cancelled && Array.isArray(data)) setVideos((prev) => (sameList(prev, data) ? prev : data));
        })
        .catch(() => {
          if (cancelled) return;
          if (retry) clearTimeout(retry);
          retry = setTimeout(load, 3000);
        });
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
      if (retry) clearTimeout(retry);
    };
  }, [libraryVersion]);
  return videos;
}

export function useProgramRows(videos: CinemaVideo[], otherLabel: string) {
  return useMemo(() => {
    const byProgram = new Map<string, CinemaVideo[]>();
    for (const v of videos) {
      const key = v.program || otherLabel;
      if (!byProgram.has(key)) byProgram.set(key, []);
      byProgram.get(key)!.push(v);
    }
    return [...byProgram.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [videos, otherLabel]);
}

export function useFeatured(videos: CinemaVideo[]) {
  const [bucket, setBucket] = useState(() => Math.floor(Date.now() / SCRAMBLE_INTERVAL_MS));
  useEffect(() => {
    const id = setInterval(() => setBucket(Math.floor(Date.now() / SCRAMBLE_INTERVAL_MS)), 60_000);
    return () => clearInterval(id);
  }, []);
  return useMemo(
    () => (videos.length === 0 ? null : videos[Math.abs((bucket * 2654435761) % videos.length)]),
    [videos, bucket],
  );
}

export function useTicker(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
