"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { chapterIndexAt, type Chapter } from "@/lib/chapters";

interface ChapterToastProps {
  chapters: Chapter[];
  videoRef: RefObject<HTMLVideoElement | null>;
  /** Libellé devant le numéro, ex. « Chapitre ». */
  label: string;
}

const VISIBLE_MS = 6000;

/** Annonce discrète du chapitre qui commence (écrans de diffusion). */
export default function ChapterToast({ chapters, videoRef, label }: ChapterToastProps) {
  const [shown, setShown] = useState<{ index: number; title: string } | null>(null);
  const lastIndex = useRef(-2);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    lastIndex.current = -2;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- l'annonce en cours ne vaut plus pour un autre cours
    setShown(null);
    if (chapters.length === 0) return;
    const id = setInterval(() => {
      const video = videoRef.current;
      if (!video || video.paused) return;
      const index = chapterIndexAt(chapters, video.currentTime);
      if (index === lastIndex.current) return;
      lastIndex.current = index;
      if (index < 0) return;
      setShown({ index, title: chapters[index].title });
      if (hideTimer.current) clearTimeout(hideTimer.current);
      hideTimer.current = setTimeout(() => setShown(null), VISIBLE_MS);
    }, 500);
    return () => {
      clearInterval(id);
      if (hideTimer.current) clearTimeout(hideTimer.current);
    };
  }, [chapters, videoRef]);

  if (!shown) return null;
  return (
    <div className="chapter-toast" role="status" key={shown.index}>
      <span className="chapter-toast__num">
        {label} {shown.index + 1}
      </span>
      <span className="chapter-toast__title">{shown.title}</span>
    </div>
  );
}
