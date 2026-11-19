import { useRef, type Dispatch, type RefObject, type SetStateAction } from "react";
import { zoomAt } from "@/lib/deviceMap";

export type View = { scale: number; tx: number; ty: number };

type Point = { x: number; y: number };

function spread(points: Map<number, Point>) {
  const [a, b] = [...points.values()];
  return { a, b, distance: Math.hypot(a.x - b.x, a.y - b.y) };
}

export function useMapPointers(
  frameRef: RefObject<HTMLDivElement | null>,
  setView: Dispatch<SetStateAction<View>>,
  interactedRef: RefObject<boolean>,
) {
  const pointers = useRef(new Map<number, Point>());
  const pinch = useRef<number | null>(null);
  const dragged = useRef(false);

  const pinchMove = () => {
    const { a, b, distance } = spread(pointers.current);
    const rect = frameRef.current?.getBoundingClientRect();
    if (rect && distance > 0) {
      const mid = { x: (a.x + b.x) / 2 - rect.left, y: (a.y + b.y) / 2 - rect.top };
      setView((v) => zoomAt(v, mid, distance / (pinch.current ?? distance)));
    }
    pinch.current = distance;
    dragged.current = true;
    interactedRef.current = true;
  };

  const onPointerDown = (event: React.PointerEvent) => {
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    dragged.current = false;
    (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
    if (pointers.current.size === 2) pinch.current = spread(pointers.current).distance;
  };
  const onPointerMove = (event: React.PointerEvent) => {
    const previous = pointers.current.get(event.pointerId);
    if (!previous) return;
    const next = { x: event.clientX, y: event.clientY };
    pointers.current.set(event.pointerId, next);
    if (pointers.current.size === 2 && pinch.current) {
      pinchMove();
      return;
    }
    const dx = next.x - previous.x;
    const dy = next.y - previous.y;
    if (dx !== 0 || dy !== 0) {
      if (Math.abs(dx) + Math.abs(dy) > 2) { dragged.current = true; interactedRef.current = true; }
      setView((v) => ({ ...v, tx: v.tx + dx, ty: v.ty + dy }));
    }
  };
  const onPointerUp = (event: React.PointerEvent) => {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
  };

  return { dragged, onPointerDown, onPointerMove, onPointerUp };
}
