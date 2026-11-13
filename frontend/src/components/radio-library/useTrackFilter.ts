"use client";

import { useMemo, useState } from "react";

import { matchesQuery } from "@/lib/searchText";

import type { Filter, RadioTrack, SortKey } from "./types";

const byText = (a: string | null, b: string | null) => (a ?? "").localeCompare(b ?? "", "fr", { sensitivity: "base" });

const SORTERS: Record<SortKey, (a: RadioTrack, b: RadioTrack) => number> = {
  recent: (a, b) => b.id - a.id,
  title: (a, b) => byText(a.title, b.title),
  artist: (a, b) => byText(a.artist, b.artist) || byText(a.title, b.title),
  duration: (a, b) => (b.duration_seconds ?? 0) - (a.duration_seconds ?? 0),
};

function passes(track: RadioTrack, filter: Filter, playlistIds: Set<number> | null): boolean {
  if (!filter) return true;
  switch (filter.type) {
    case "artist": return track.artist === filter.value || track.album_artist === filter.value;
    case "album": return track.album === filter.value;
    case "genre": return track.genre === filter.value;
    case "tag": return track.tags.includes(filter.value);
    case "playlist": return playlistIds?.has(track.id) ?? false;
  }
}

export function useTrackFilter(tracks: RadioTrack[]) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>(null);
  const [playlistIds, setPlaylistIds] = useState<Set<number> | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("recent");
  const query = search.trim();

  const genres = useMemo(() => {
    const counts = new Map<string, number>();
    tracks.forEach((tr) => {
      if (tr.genre) counts.set(tr.genre, (counts.get(tr.genre) ?? 0) + 1);
    });
    return Array.from(counts.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => a.name.localeCompare(b.name));
  }, [tracks]);

  const suggestions = useMemo(() => tracks.flatMap((tr) => [tr.title, tr.artist, tr.album, tr.genre].filter((x): x is string => !!x)), [tracks]);

  const sorted = useMemo(() => {
    const shown = tracks.filter((tr) =>
      (!query || matchesQuery(`${tr.title} ${tr.artist ?? ""} ${tr.album ?? ""} ${tr.genre ?? ""}`, query)) && passes(tr, filter, playlistIds));
    return shown.sort(SORTERS[sortKey]);
  }, [tracks, query, filter, playlistIds, sortKey]);

  const apply = (next: Filter, ids: Set<number> | null = null) => {
    setFilter(next);
    setPlaylistIds(ids);
  };

  return { search, setSearch, filter, sortKey, setSortKey, genres, suggestions, sorted, apply, clear: () => apply(null) };
}

export type TrackFilter = ReturnType<typeof useTrackFilter>;

export function filterIcon(filter: Filter): string {
  if (!filter) return "library_music";
  return { tag: "label", genre: "graphic_eq", playlist: "queue_music", album: "album", artist: "person" }[filter.type];
}
