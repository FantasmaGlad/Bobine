"use client";

import React, { useState } from "react";
import ChapterList from "@/components/ChapterList";
import ChapterTicks from "@/components/ChapterTicks";
import type { Chapter } from "@/lib/chapters";
import { formatTime } from "@/lib/format";

interface RemoteSeekProps {
  position: number;
  duration: number | null | undefined;
  chapters: Chapter[];
  disabled?: boolean;
  onSeek: (seconds: number) => void;
}

export default function RemoteSeek({ position, duration, chapters, disabled, onSeek }: RemoteSeekProps) {
  const [dragValue, setDragValue] = useState<number | null>(null);
  const shown = dragValue ?? position;
  const release = (e: React.SyntheticEvent<HTMLInputElement>) => {
    onSeek(Number((e.target as HTMLInputElement).value));
    setDragValue(null);
  };
  return (
    <>
      <div className="mobile-remote-progress">
        <div className="chapter-seek">
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={1}
            value={shown}
            disabled={disabled}
            onChange={(e) => setDragValue(Number(e.target.value))}
            onMouseUp={release}
            onTouchEnd={release}
            className="seek-slider mobile-remote-seek"
          />
          <ChapterTicks chapters={chapters} duration={duration || 0} />
        </div>
        <div className="now-card__times">
          <span>{formatTime(shown)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>
      <ChapterList chapters={chapters} position={shown} onSeek={onSeek} />
    </>
  );
}
