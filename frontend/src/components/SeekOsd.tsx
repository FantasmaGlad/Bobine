"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Chapter } from "@/lib/chapters";
import { chapterIndexAt } from "@/lib/chapters";
import ChapterTicks from "@/components/ChapterTicks";

export interface SeekHud {
  position: number;
  duration: number;
}

const SEEK_HUD_MS = 2800;

function formatTime(seconds: number) {
  const total = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  return `${Math.floor(total / 60)}:${Math.floor(total % 60).toString().padStart(2, "0")}`;
}

export function useSeekHud(): [SeekHud & { visible: boolean }, (next: SeekHud) => void] {
  const [hud, setHud] = useState<SeekHud & { visible: boolean }>({ position: 0, duration: 0, visible: false });
  const timer = useRef<number | null>(null);
  const show = useCallback((next: SeekHud) => {
    setHud({ ...next, visible: true });
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setHud((prev) => ({ ...prev, visible: false })), SEEK_HUD_MS);
  }, []);
  useEffect(() => () => { if (timer.current !== null) window.clearTimeout(timer.current); }, []);
  return [hud, show];
}

export default function SeekOsd({ position, duration, visible, chapters }: SeekHud & { visible: boolean; chapters: Chapter[] }) {
  const index = chapterIndexAt(chapters, position);
  const title = index >= 0 ? chapters[index].title : "";
  const ratio = duration > 0 ? Math.min(1, Math.max(0, position / duration)) : 0;
  return (
    <div className={`seek-osd ${visible ? "is-visible" : ""}`} role="status" aria-live="off">
      <div className="seek-osd-line">
        <span className="seek-osd-time">{formatTime(position)}</span>
        <div className="seek-osd-track">
          <span className="seek-osd-fill" style={{ transform: `scaleX(${ratio})` }} />
          <ChapterTicks chapters={chapters} duration={duration} />
        </div>
        <span className="seek-osd-time">{formatTime(duration)}</span>
      </div>
      {title && <div className="seek-osd-chapter">{title}</div>}
    </div>
  );
}
