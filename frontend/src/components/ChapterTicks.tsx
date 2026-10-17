"use client";

import type { Chapter } from "@/lib/chapters";

/** Repères de chapitres à poser dans un conteneur `position: relative` autour d'une barre de lecture. */
export default function ChapterTicks({ chapters, duration }: { chapters: Chapter[]; duration: number }) {
  if (!duration || chapters.length === 0) return null;
  return (
    <span className="chapter-ticks" aria-hidden="true">
      {chapters
        .filter((chapter) => chapter.start_seconds > 0.5 && chapter.start_seconds < duration)
        .map((chapter) => (
          <span key={chapter.id} className="chapter-tick" style={{ left: `${(chapter.start_seconds / duration) * 100}%` }} title={chapter.title} />
        ))}
    </span>
  );
}
