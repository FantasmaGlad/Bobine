export const OVERSCAN_ROWS = 8;

export function visibleRange(scrollTop: number, viewport: number, pitch: number, count: number, overscan = OVERSCAN_ROWS): [number, number] {
  if (count === 0) return [0, 0];
  if (pitch <= 0) return [0, Math.min(count, overscan)];
  const start = Math.max(0, Math.floor(scrollTop / pitch) - overscan);
  const end = Math.min(count, Math.ceil((scrollTop + viewport) / pitch) + overscan);
  return [Math.min(start, end), end];
}

export function dropIndex(contentY: number, pitch: number, rowHeight: number, count: number): number {
  if (count === 0) return 0;
  const index = Math.floor((contentY - rowHeight) / pitch) + 1;
  return index >= count ? count - 1 : Math.max(0, index);
}
