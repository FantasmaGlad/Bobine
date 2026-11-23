"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { chapterIndexAt, type Chapter, type ChapterToastPlacement } from "@/lib/chapters";

interface ChapterToastProps {
  chapters: Chapter[];
  videoRef: RefObject<HTMLVideoElement | null>;
  label: string;
  placement: ChapterToastPlacement;
}

const VISIBLE_MS = 6000;

export default function ChapterToast({ chapters, videoRef, label, placement }: ChapterToastProps) {
  const [shown, setShown] = useState<{ index: number; title: string } | null>(null);
  const lastIndex = useRef(-2);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [shownFor, setShownFor] = useState(chapters);
  if (shownFor !== chapters) {
    setShownFor(chapters);
    setShown(null);
  }

  useEffect(() => {
    lastIndex.current = -2;
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

  if (!shown || placement === "hidden") return null;
  return (
    <div className={`chapter-toast ${placement === "lifted" ? "is-lifted" : ""}`} role="status" key={shown.index}>
      <span className="chapter-toast__num">
        {label} {shown.index + 1}
      </span>
      <span className="chapter-toast__title">{shown.title}</span>
    </div>
  );
}
