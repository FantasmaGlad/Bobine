"use client";

import React, { useRef } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { RadioTrackInfo } from "@/lib/useRadioSocket";
import QueueRow from "./radio-queue/QueueRow";
import { dragOffset, useQueueDrag } from "./radio-queue/useQueueDrag";
import { useQueueOrder } from "./radio-queue/useQueueOrder";

interface RadioQueueListProps {
  tracks: RadioTrackInfo[];
  baseIndex: number;
  getApiUrl: (path: string) => string;
  onRemove: (absoluteIndex: number) => void;
  onMove: (fromAbsoluteIndex: number, toAbsoluteIndex: number) => void;
}

export default function RadioQueueList({ tracks, baseIndex, getApiUrl, onRemove, onMove }: RadioQueueListProps) {
  const { t } = useAppSettings();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rowRefs = useRef<(HTMLDivElement | null)[]>([]);
  const { shown, applyLocalMove, handleHandleKey } = useQueueOrder(tracks, baseIndex, onMove, containerRef);
  const { drag, startDrag, moveDrag, endDrag } = useQueueDrag(containerRef, rowRefs, shown.length, applyLocalMove);

  return (
    <div ref={containerRef} className={`rq-list${drag ? " is-sorting" : ""}`} role="list">
      {shown.map((track, i) => {
        const absolute = baseIndex + i;
        return (
          <QueueRow
            key={`${absolute}-${track.id}`}
            track={track}
            index={i}
            cover={track.cover_url ? getApiUrl(track.cover_url) : null}
            offset={dragOffset(drag, i)}
            dragged={drag?.from === i}
            rowRef={(node) => {
              rowRefs.current[i] = node;
            }}
            handle={{
              onPointerDown: (event) => startDrag(event, i),
              onPointerMove: moveDrag,
              onPointerUp: (event) => endDrag(event, true),
              onPointerCancel: (event) => endDrag(event, false),
              onKeyDown: (event) => handleHandleKey(event, i),
            }}
            onRemove={() => onRemove(absolute)}
            t={t}
          />
        );
      })}
    </div>
  );
}
