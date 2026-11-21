"use client";

import React, { memo, useRef } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useListWindow } from "@/lib/useListWindow";
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

function RadioQueueList({ tracks, baseIndex, getApiUrl, onRemove, onMove }: RadioQueueListProps) {
  const { t } = useAppSettings();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rowRefs = useRef<(HTMLDivElement | null)[]>([]);
  const { shown, applyLocalMove, handleHandleKey } = useQueueOrder(tracks, baseIndex, onMove, containerRef);
  const view = useListWindow(containerRef, shown.length);
  const { drag, startDrag, moveDrag, endDrag } = useQueueDrag(containerRef, rowRefs, shown.length, view.pitch, applyLocalMove);
  const start = drag ? Math.min(view.start, drag.from) : view.start;
  const end = drag ? Math.max(view.end, drag.from + 1) : view.end;

  return (
    <div
      ref={containerRef}
      className={`rq-list${drag ? " is-sorting" : ""}`}
      role="list"
      onScroll={view.onScroll}
    >
      {start > 0 && <div aria-hidden="true" style={{ height: start * view.pitch - view.gap, flexShrink: 0 }} />}
      {shown.slice(start, end).map((track, offset) => {
        const i = start + offset;
        const absolute = baseIndex + i;
        return (
          <QueueRow
            key={`${absolute}-${track.id}`}
            track={track}
            index={i}
            total={shown.length}
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
      {end < shown.length && <div aria-hidden="true" style={{ height: (shown.length - end) * view.pitch - view.gap, flexShrink: 0 }} />}
    </div>
  );
}

export default memo(RadioQueueList);
