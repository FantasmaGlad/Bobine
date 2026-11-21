import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { visibleRange } from "@/lib/listWindow";

const DEFAULT_PITCH = 72;
const DEFAULT_VIEWPORT = 600;

export function useListWindow(containerRef: RefObject<HTMLElement | null>, count: number) {
  const [scrollTop, setScrollTop] = useState(0);
  const [viewport, setViewport] = useState(0);
  const [pitch, setPitch] = useState(DEFAULT_PITCH);
  const [gap, setGap] = useState(0);
  const frameRef = useRef<number | null>(null);
  const hasRows = count > 0;

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const measure = () => {
      setViewport(container.clientHeight);
      const rowGap = parseFloat(getComputedStyle(container).rowGap) || 0;
      const row = container.querySelector<HTMLElement>('[role="listitem"]');
      setGap(rowGap);
      if (row) setPitch(row.offsetHeight + rowGap);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    return () => observer.disconnect();
  }, [containerRef, hasRows]);

  useEffect(() => () => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
  }, []);

  const onScroll = useCallback(() => {
    if (frameRef.current !== null) return;
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = null;
      setScrollTop(containerRef.current?.scrollTop ?? 0);
    });
  }, [containerRef]);

  const [start, end] = visibleRange(scrollTop, viewport || DEFAULT_VIEWPORT, pitch, count);
  return { start, end, pitch, gap, onScroll };
}
