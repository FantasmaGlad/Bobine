export interface ScrollNode {
  parentElement: ScrollNode | null;
  scrollHeight: number;
  clientHeight: number;
}

export function scrollContainerOf<T extends ScrollNode>(element: T, overflowY: (node: T) => string): T | null {
  for (let node = element.parentElement as T | null; node; node = node.parentElement as T | null) {
    const overflow = overflowY(node);
    if ((overflow === "auto" || overflow === "scroll") && node.scrollHeight > node.clientHeight) return node;
  }
  return null;
}

export function edgeFallbackIndex(current: number, length: number, direction: "left" | "right" | "up" | "down"): number {
  if (direction === "up" || direction === "down") return current;
  return (current + (direction === "right" ? 1 : -1) + length) % length;
}
