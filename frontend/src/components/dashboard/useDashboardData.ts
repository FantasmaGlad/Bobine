"use client";

import { useEffect, useState } from "react";

import { getApiUrl } from "@/lib/apiUrl";
import type { PlaybackChannel } from "@/lib/usePlaybackSocket";

import type { BackgroundSummary, InterruptedState, OccurrenceSummary, PlaylistSummary, VideoSummary } from "./types";

const DAY_MS = 24 * 60 * 60 * 1000;

function loadList<T>(path: string, set: (items: T[]) => void) {
  fetch(getApiUrl(path), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : []))
    .then(set)
    .catch(() => set([]));
}

export function useDashboardData(channel: PlaybackChannel) {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [upcoming, setUpcoming] = useState<OccurrenceSummary[]>([]);
  const [backgrounds, setBackgrounds] = useState<BackgroundSummary[]>([]);
  const [interrupted, setInterrupted] = useState<InterruptedState | null>(null);
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    const fetchInterrupted = () => {
      fetch(getApiUrl(`/playback/interrupted?channel=${channel}`), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then(setInterrupted)
        .catch(() => setInterrupted(null));
    };
    const now = new Date();
    const horizon = new Date(now.getTime() + 14 * DAY_MS);
    loadList<OccurrenceSummary>(`/schedule/occurrences?start=${now.toISOString()}&end=${horizon.toISOString()}&channel=${channel}`,
      (data) => setUpcoming(data.filter((o) => o.override_action !== "cancelled").slice(0, 3)));
    loadList("/backgrounds", setBackgrounds);
    loadList("/videos?sort_by=imported_at&order=desc", setVideos);
    loadList("/playlists", setPlaylists);
    fetchInterrupted();
    const id = setInterval(fetchInterrupted, 10000);
    return () => clearInterval(id);
  }, [channel]);

  const resume = async () => {
    setResuming(true);
    try {
      const res = await fetch(getApiUrl(`/playback/interrupted/resume?channel=${channel}`), { method: "POST" });
      if (res.ok) setInterrupted(null);
    } finally {
      setResuming(false);
    }
  };

  const dismiss = async () => {
    await fetch(getApiUrl(`/playback/interrupted?channel=${channel}`), { method: "DELETE" });
    setInterrupted(null);
  };

  return { videos, playlists, upcoming, backgrounds, interrupted, resuming, resume, dismiss };
}

export type DashboardData = ReturnType<typeof useDashboardData>;

export function setDisplayOutput(channel: string, output: string) {
  fetch(getApiUrl("/settings/display-output"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel, output }),
  }).catch(() => {});
}
