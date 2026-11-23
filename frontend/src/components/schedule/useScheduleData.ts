"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { addDays, isSameLocalDay, type ChannelValue, type Occurrence, type PlaylistSummary, type RadioPlaylistSummary, type VideoSummary } from "@/lib/scheduleTime";
import type { ShowToast } from "@/lib/useToast";
import { isRadioChannel, outputOfRadio } from "@/lib/outputs";

const byRunAt = (a: Occurrence, b: Occurrence) => new Date(a.run_at).getTime() - new Date(b.run_at).getTime();

function loadList<T>(path: string, set: (items: T[]) => void) {
  fetch(getApiUrl(path), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : []))
    .then(set)
    .catch(() => set([]));
}

export function useScheduleCatalog() {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [playlists, setPlaylists] = useState<PlaylistSummary[]>([]);
  const [radioPlaylists, setRadioPlaylists] = useState<RadioPlaylistSummary[]>([]);
  useEffect(() => {
    loadList("/videos?sort_by=imported_at&order=desc", setVideos);
    loadList("/playlists", setPlaylists);
    loadList("/radio/playlists", setRadioPlaylists);
  }, []);
  return { videos, playlists, radioPlaylists };
}

export type ScheduleCatalog = ReturnType<typeof useScheduleCatalog>;

export function useRadioLaneOutput(channel: ChannelValue) {
  const [read, setRead] = useState<{ channel: ChannelValue; mode: string } | null>(null);
  useEffect(() => {
    if (!isRadioChannel(channel)) return;
    const output = outputOfRadio(channel).id;
    let cancelled = false;
    fetch(getApiUrl(`/outputs/${output}`), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data && typeof data.mode === "string") setRead({ channel, mode: data.mode });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [channel]);
  return read?.channel === channel ? read.mode : null;
}

export function useOccurrences(weekStart: Date, channel: ChannelValue, showToast: ShowToast) {
  const { t } = useAppSettings();
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [loading, setLoading] = useState(true);
  const weekEnd = useMemo(() => addDays(weekStart, 7), [weekStart]);
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);

  const refresh = useCallback(() => Promise.resolve()
    .then(() => {
      setLoading(true);
      const params = new URLSearchParams({ start: weekStart.toISOString(), end: weekEnd.toISOString(), channel });
      return fetch(getApiUrl(`/schedule/occurrences?${params.toString()}`), { cache: "no-store" });
    })
    .then(async (res) => {
      if (res.ok) setOccurrences(await res.json());
      else showToast(t("schedule.fetchError"), "error");
    })
    .catch(() => showToast(t("schedule.fetchNetworkError"), "error"))
    .finally(() => setLoading(false)), [weekStart, weekEnd, channel, showToast, t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const byDay = useMemo(
    () => weekDays.map((day) => occurrences.filter((o) => isSameLocalDay(new Date(o.run_at), day)).sort(byRunAt)),
    [occurrences, weekDays]
  );

  return { occurrences, loading, weekDays, weekEnd, byDay, refresh };
}
