import { useCallback, useEffect, useRef, useState } from "react";
import { fitView, zoomAt, type MapLayout } from "@/lib/deviceMap";
import { useMapPointers, type View } from "./useMapPointers";

type Layout = MapLayout;

function useFrameSize(frameRef: React.RefObject<HTMLDivElement | null>, hasLayout: boolean) {
  const [size, setSize] = useState({ width: 800, height: 520 });
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => setSize({ width: frame.clientWidth, height: frame.clientHeight }));
    observer.observe(frame);
    setSize({ width: frame.clientWidth, height: frame.clientHeight });
    return () => observer.disconnect();
  }, [frameRef, hasLayout]);
  return size;
}

export function useMapViewport(layout: Layout | null) {
  const [view, setView] = useState<View>({ scale: 1, tx: 0, ty: 0 });
  const frameRef = useRef<HTMLDivElement>(null);
  const interacted = useRef(false);
  const hasLayout = layout !== null;
  const size = useFrameSize(frameRef, hasLayout);

  const recenter = useCallback(() => {
    interacted.current = false;
    if (layout) setView(fitView(layout.bounds, size));
  }, [layout, size]);

  useEffect(() => {
    if (layout && !interacted.current && size.width > 50) setView(fitView(layout.bounds, size));
  }, [layout, size]);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      interacted.current = true;
      const rect = frame.getBoundingClientRect();
      const point = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      setView((v) => zoomAt(v, point, Math.exp(-event.deltaY * 0.0015)));
    };
    frame.addEventListener("wheel", onWheel, { passive: false });
    return () => frame.removeEventListener("wheel", onWheel);
  }, [hasLayout]);

  const pointerHandlers = useMapPointers(frameRef, setView, interacted);
  const zoomCenter = (factor: number, markInteracted: boolean) => {
    if (markInteracted) interacted.current = true;
    setView((v) => zoomAt(v, { x: size.width / 2, y: size.height / 2 }, factor));
  };
  const markInteracted = () => { interacted.current = true; };

  return { view, size, frameRef, recenter, zoomCenter, markInteracted, ...pointerHandlers };
}

export type MapViewport = ReturnType<typeof useMapViewport>;
