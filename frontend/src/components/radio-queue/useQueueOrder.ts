import { useEffect, useRef, useState, type RefObject } from "react";
import type { RadioTrackInfo } from "@/lib/useRadioSocket";

const OPTIMISTIC_HOLD_MS = 1500;

export function useQueueOrder(
  tracks: RadioTrackInfo[],
  baseIndex: number,
  onMove: (from: number, to: number) => void,
  containerRef: RefObject<HTMLDivElement | null>,
) {
  const [override, setOverride] = useState<{ signature: string; tracks: RadioTrackInfo[] } | null>(null);
  const overrideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const focusHandleRef = useRef<number | null>(null);
  const signature = `${baseIndex}:${tracks.map((track) => track.id).join(",")}`;
  const shown = override && override.signature === signature ? override.tracks : tracks;

  useEffect(
    () => () => {
      if (overrideTimerRef.current) clearTimeout(overrideTimerRef.current);
    },
    [],
  );

  useEffect(() => {
    if (focusHandleRef.current === null) return;
    const index = focusHandleRef.current;
    focusHandleRef.current = null;
    containerRef.current?.querySelector<HTMLElement>(`[data-handle="${index}"]`)?.focus();
  }, [shown, containerRef]);

  const applyLocalMove = (from: number, to: number) => {
    const next = [...shown];
    next.splice(to, 0, next.splice(from, 1)[0]);
    setOverride({ signature, tracks: next });
    if (overrideTimerRef.current) clearTimeout(overrideTimerRef.current);
    overrideTimerRef.current = setTimeout(() => setOverride(null), OPTIMISTIC_HOLD_MS);
    onMove(baseIndex + from, baseIndex + to);
  };

  const handleHandleKey = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    const delta = event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0;
    if (!delta) return;
    event.preventDefault();
    const to = index + delta;
    if (to < 0 || to >= shown.length) return;
    focusHandleRef.current = to;
    applyLocalMove(index, to);
  };

  return { shown, applyLocalMove, handleHandleKey };
}
