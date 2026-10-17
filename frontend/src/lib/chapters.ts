"use client";

import { useEffect, useState } from "react";

export interface Chapter {
  id: number;
  position: number;
  start_seconds: number;
  end_seconds: number | null;
  title: string;
}

/** Chapitres d'un cours (liste vide sans vidéo, sans chapitre ou en cas d'échec). */
export function useVideoChapters(videoId: number | null | undefined, getApiUrl: (path: string) => string): Chapter[] {
  const [chapters, setChapters] = useState<Chapter[]>([]);

  useEffect(() => {
    if (!videoId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- remise à zéro quand le cours disparaît (état dérivé d'une requête externe)
      setChapters([]);
      return;
    }
    let cancelled = false;
    fetch(getApiUrl(`/videos/${videoId}/chapters`))
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (!cancelled) setChapters(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (!cancelled) setChapters([]);
      });
    return () => {
      cancelled = true;
    };
    // getApiUrl est une fonction pure propre à chaque page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  return chapters;
}

/** Indice du chapitre en cours à cette position, -1 avant le premier. */
export function chapterIndexAt(chapters: Chapter[], position: number): number {
  let index = -1;
  for (let i = 0; i < chapters.length; i++) {
    if (chapters[i].start_seconds <= position + 0.25) index = i;
    else break;
  }
  return index;
}
