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

/**
 * Position où sauter pour le chapitre suivant ou précédent (touches de chaîne de la télécommande), ou `null` si rien
 * ne change. « Précédent » revient d'abord au début du chapitre en cours quand on y est depuis plus de 3 s.
 */
export function chapterJumpTarget(chapters: Chapter[], position: number, direction: "next" | "prev"): number | null {
  if (!chapters.length) return null;
  const index = chapterIndexAt(chapters, position);
  if (direction === "next") return index + 1 < chapters.length ? chapters[index + 1].start_seconds : null;
  if (index >= 0 && position - chapters[index].start_seconds > 3) return chapters[index].start_seconds;
  return index >= 1 ? chapters[index - 1].start_seconds : 0;
}
