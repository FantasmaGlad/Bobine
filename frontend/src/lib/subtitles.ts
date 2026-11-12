"use client";

import { useEffect, useState, type RefObject } from "react";

export interface SubtitleTrack {
  id: number;
  language_code: string;
  language_label: string;
  vtt_url: string;
}

export function subtitleSrc(getApiUrl: (path: string) => string, vttUrl: string): string {
  return getApiUrl(vttUrl.replace(/^\/api(?=\/)/, ""));
}

export function useVideoSubtitles(
  videoId: number | null | undefined,
  getApiUrl: (path: string) => string,
): SubtitleTrack[] {
  const [tracks, setTracks] = useState<SubtitleTrack[]>([]);

  useEffect(() => {
    if (!videoId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- remise à zéro quand le cours disparaît (état dérivé d'une requête externe)
      setTracks([]);
      return;
    }
    let cancelled = false;
    fetch(getApiUrl(`/videos/${videoId}/subtitles`))
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (!cancelled) setTracks(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (!cancelled) setTracks([]);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  return tracks;
}

export function applySubtitleMode(
  video: HTMLVideoElement | null,
  tracks: SubtitleTrack[],
  activeId: number | "off" | null,
): void {
  if (!video) return;
  const wanted = activeId === "off" ? null : activeId ?? tracks[0]?.id ?? null;
  video.querySelectorAll("track").forEach((el) => {
    const id = Number(el.dataset.subtitleId);
    el.track.mode = wanted !== null && id === wanted ? "showing" : "disabled";
  });
}

export function useApplySubtitleMode(
  videoRefs: Array<RefObject<HTMLVideoElement | null>>,
  tracks: SubtitleTrack[],
  activeId: number | "off" | null,
): void {
  useEffect(() => {
    videoRefs.forEach((ref) => applySubtitleMode(ref.current, tracks, activeId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tracks, activeId]);
}
