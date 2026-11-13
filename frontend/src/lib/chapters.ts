"use client";

import { useVideoList } from "./useVideoList.ts";

export interface Chapter {
  id: number;
  position: number;
  start_seconds: number;
  end_seconds: number | null;
  title: string;
}

export function useVideoChapters(videoId: number | null | undefined, getApiUrl: (path: string) => string): Chapter[] {
  return useVideoList<Chapter>(videoId, getApiUrl, "chapters");
}

export function chapterIndexAt(chapters: Chapter[], position: number): number {
  let index = -1;
  for (let i = 0; i < chapters.length; i++) {
    if (chapters[i].start_seconds <= position + 0.25) index = i;
    else break;
  }
  return index;
}

export function chapterJumpTarget(chapters: Chapter[], position: number, direction: "next" | "prev"): number | null {
  if (!chapters.length) return null;
  const index = chapterIndexAt(chapters, position);
  if (direction === "next") return index + 1 < chapters.length ? chapters[index + 1].start_seconds : null;
  if (index >= 0 && position - chapters[index].start_seconds > 3) return chapters[index].start_seconds;
  return index >= 1 ? chapters[index - 1].start_seconds : 0;
}
