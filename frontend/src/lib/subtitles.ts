"use client";

import { useEffect, type RefObject } from "react";
import { useVideoList } from "./useVideoList.ts";

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
  return useVideoList<SubtitleTrack>(videoId, getApiUrl, "subtitles");
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
  }, [videoRefs, tracks, activeId]);
}
