import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

export type Edge = "none" | "start" | "middle" | "end";

export function useSegmentedIndicator(value: string, count: number) {
  const trackRef = useRef<HTMLDivElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null);
  const [edge, setEdge] = useState<Edge>("none");

  const updateEdge = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    if (el.scrollWidth <= el.clientWidth + 1) setEdge("none");
    else if (el.scrollLeft <= 2) setEdge("start");
    else if (el.scrollLeft >= el.scrollWidth - el.clientWidth - 2) setEdge("end");
    else setEdge("middle");
  }, []);

  const measure = useCallback(() => {
    const track = trackRef.current;
    const active = track?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
    if (!track || !active) return;
    setIndicator({ left: active.offsetLeft, width: active.offsetWidth });
    active.scrollIntoView({ inline: "center", block: "nearest" });
    updateEdge();
  }, [updateEdge]);

  useLayoutEffect(() => {
    measure();
  }, [measure, value, count]);

  useEffect(() => {
    const track = trackRef.current;
    if (!track || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measure());
    observer.observe(track);
    document.fonts?.ready.then(measure).catch(() => undefined);
    return () => observer.disconnect();
  }, [measure]);

  return { trackRef, scrollerRef, indicator, edge, updateEdge };
}
