import { useCallback, useEffect, useLayoutEffect, useState, type RefObject } from "react";

export const POPOVER_MAX_HEIGHT = 380;
const POPOVER_MIN_WIDTH = 340;

export interface PopoverAnchor {
  left: number;
  top: number;
  width: number;
  above: boolean;
}

export function usePopoverAnchor(
  active: boolean,
  triggerRef: RefObject<HTMLButtonElement | null>,
  popoverRef: RefObject<HTMLDivElement | null>,
  onOutside: () => void,
): PopoverAnchor | null {
  const [anchor, setAnchor] = useState<PopoverAnchor | null>(null);

  const measure = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const above = spaceBelow < Math.min(POPOVER_MAX_HEIGHT, 260) && rect.top > spaceBelow;
    const width = Math.max(rect.width, POPOVER_MIN_WIDTH);
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
    setAnchor({ left, top: above ? rect.top - 4 : rect.bottom + 4, width, above });
  }, [triggerRef]);

  useLayoutEffect(() => {
    if (!active) return;
    measure();
    const onChangeViewport = () => measure();
    window.addEventListener("resize", onChangeViewport);
    window.addEventListener("scroll", onChangeViewport, true);
    return () => {
      window.removeEventListener("resize", onChangeViewport);
      window.removeEventListener("scroll", onChangeViewport, true);
    };
  }, [active, measure]);

  useEffect(() => {
    if (!active) return;
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (popoverRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      onOutside();
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [active, onOutside, popoverRef, triggerRef]);

  return anchor;
}
