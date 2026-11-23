import { edgeFallbackIndex, scrollContainerOf } from "../scrollContainer.ts";

export const REMOTE_FOCUS_CLASS = "kiosk-remote-focus";

export const REMOTE_SCROLL_TOP_ATTR = "data-remote-scroll-top";

export function selectRemoteTarget(items: HTMLElement[], el: HTMLElement): void {
  for (const it of items) it.classList.toggle(REMOTE_FOCUS_CLASS, it === el);
  el.focus();
  if (el.closest(`[${REMOTE_SCROLL_TOP_ATTR}]`)) {
    (scrollContainerOf(el, (node) => getComputedStyle(node).overflowY) ?? window).scrollTo({ top: 0, behavior: "smooth" });
  } else {
    el.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }
}

export function moveDomFocus2D(
  selector: string,
  direction: "left" | "right" | "up" | "down"
): void {
  if (typeof document === "undefined") return;
  const items = Array.from(document.querySelectorAll<HTMLElement>(selector)).filter(
    (el) => el.offsetParent !== null && !el.hasAttribute("disabled")
  );
  if (items.length === 0) return;

  const active = document.activeElement as HTMLElement | null;
  let currentIndex = items.findIndex((el) => el.classList.contains(REMOTE_FOCUS_CLASS));
  if (currentIndex < 0 && active) currentIndex = items.indexOf(active);

  if (currentIndex < 0) {
    selectRemoteTarget(items, items[0]);
    return;
  }

  const currentEl = items[currentIndex];
  const currentRect = currentEl.getBoundingClientRect();
  const currentCx = currentRect.left + currentRect.width / 2;
  const currentCy = currentRect.top + currentRect.height / 2;

  let bestItem: HTMLElement | null = null;
  let bestScore = Infinity;

  for (let i = 0; i < items.length; i++) {
    if (i === currentIndex) continue;
    const it = items[i];
    const r = it.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;

    const dx = cx - currentCx;
    const dy = cy - currentCy;

    let inDirection = false;
    let mainDist = 0;
    let crossDist = 0;

    switch (direction) {
      case "left":
        if (dx < -6) {
          inDirection = true;
          mainDist = -dx;
          crossDist = Math.abs(dy);
        }
        break;
      case "right":
        if (dx > 6) {
          inDirection = true;
          mainDist = dx;
          crossDist = Math.abs(dy);
        }
        break;
      case "up":
        if (dy < -6) {
          inDirection = true;
          mainDist = -dy;
          crossDist = Math.abs(dx);
        }
        break;
      case "down":
        if (dy > 6) {
          inDirection = true;
          mainDist = dy;
          crossDist = Math.abs(dx);
        }
        break;
    }

    if (inDirection) {
      const score = mainDist + crossDist * 2.2;
      if (score < bestScore) {
        bestScore = score;
        bestItem = it;
      }
    }
  }

  const targetEl = bestItem ?? items[edgeFallbackIndex(currentIndex, items.length, direction)];

  if (targetEl) selectRemoteTarget(items, targetEl);
}

export function moveDomFocus(selector: string, direction: 1 | -1): void {
  if (typeof document === "undefined") return;
  const items = Array.from(document.querySelectorAll<HTMLElement>(selector)).filter(
    (el) => el.offsetParent !== null && !el.hasAttribute("disabled")
  );
  if (items.length === 0) return;
  const active = document.activeElement as HTMLElement | null;
  let at = items.findIndex((el) => el.classList.contains(REMOTE_FOCUS_CLASS));
  if (at < 0 && active) at = items.indexOf(active);
  const next = at < 0 ? (direction === 1 ? 0 : items.length - 1) : (at + direction + items.length) % items.length;
  selectRemoteTarget(items, items[next]);
}

export function activateDomFocus(selector: string): void {
  if (typeof document === "undefined") return;
  const items = Array.from(document.querySelectorAll<HTMLElement>(selector)).filter(
    (el) => el.offsetParent !== null && !el.hasAttribute("disabled")
  );
  if (items.length === 0) return;
  const marked = items.find((el) => el.classList.contains(REMOTE_FOCUS_CLASS));
  const active = document.activeElement as HTMLElement | null;
  (marked ?? (active && items.includes(active) ? active : items[0])).click();
}
