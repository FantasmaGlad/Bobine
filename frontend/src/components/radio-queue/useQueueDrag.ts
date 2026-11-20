import { useState, type RefObject } from "react";

const AUTOSCROLL_EDGE = 36;
const AUTOSCROLL_STEP = 14;

export interface DragState {
  from: number;
  to: number;
  startY: number;
  startScroll: number;
  dy: number;
  rowHeight: number;
  bottoms: number[];
}

export function dragOffset(drag: DragState | null, index: number): number {
  if (!drag) return 0;
  if (index === drag.from) return drag.dy;
  if (drag.from < drag.to && index > drag.from && index <= drag.to) return -drag.rowHeight;
  if (drag.from > drag.to && index >= drag.to && index < drag.from) return drag.rowHeight;
  return 0;
}

function releaseCapture(event: React.PointerEvent<HTMLButtonElement>) {
  try {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  } catch {
  }
}

export function useQueueDrag(
  containerRef: RefObject<HTMLDivElement | null>,
  rowsRef: RefObject<(HTMLDivElement | null)[]>,
  count: number,
  commitMove: (from: number, to: number) => void,
) {
  const [drag, setDrag] = useState<DragState | null>(null);

  const startDrag = (event: React.PointerEvent<HTMLButtonElement>, index: number) => {
    if (event.button !== 0 && event.pointerType === "mouse") return;
    const container = containerRef.current;
    if (!container) return;
    event.preventDefault();
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
    }
    const containerTop = container.getBoundingClientRect().top;
    const bottoms = rowsRef.current
      .slice(0, count)
      .map((row) => (row ? row.getBoundingClientRect().bottom - containerTop + container.scrollTop : 0));
    const rect = rowsRef.current[index]?.getBoundingClientRect();
    setDrag({ from: index, to: index, startY: event.clientY, startScroll: container.scrollTop, dy: 0, rowHeight: (rect?.height ?? 56) + 8, bottoms });
  };

  const moveDrag = (event: React.PointerEvent<HTMLButtonElement>) => {
    const container = containerRef.current;
    if (!drag || !container) return;
    const bounds = container.getBoundingClientRect();
    if (event.clientY < bounds.top + AUTOSCROLL_EDGE) container.scrollTop -= AUTOSCROLL_STEP;
    else if (event.clientY > bounds.bottom - AUTOSCROLL_EDGE) container.scrollTop += AUTOSCROLL_STEP;
    const contentY = event.clientY - bounds.top + container.scrollTop;
    let to = drag.bottoms.findIndex((bottom) => contentY < bottom);
    if (to < 0) to = Math.max(0, count - 1);
    const dy = event.clientY - drag.startY + (container.scrollTop - drag.startScroll);
    setDrag({ ...drag, to, dy });
  };

  const endDrag = (event: React.PointerEvent<HTMLButtonElement>, commit: boolean) => {
    if (!drag) return;
    releaseCapture(event);
    const { from, to } = drag;
    setDrag(null);
    if (commit && to !== from) commitMove(from, to);
  };

  return { drag, startDrag, moveDrag, endDrag };
}
