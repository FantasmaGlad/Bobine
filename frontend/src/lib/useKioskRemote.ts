"use client";

import { useEffect, useRef } from "react";
import {
  ANALOG_TRIGGERS, GAMEPAD_DIRECTIONS, REMOTE_ACTIONS, gamepadBindings, keyBinding, pickHandler,
  type RemoteActionHandlers,
} from "./remoteBindings.ts";
import { edgeFallbackIndex, scrollContainerOf } from "./scrollContainer.ts";
import { currentRemoteBindings, loadRemoteBindings } from "./remoteBindingsStore.ts";

export interface RemoteHandlers {
  onLeft?: () => void;
  onRight?: () => void;
  onUp?: () => void;
  onDown?: () => void;
  onEnter?: () => void;
  onBack?: () => void;
  onPlayPause?: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  onChapterNext?: () => void;
  onChapterPrev?: () => void;
  onVolumeUp?: () => void;
  onVolumeDown?: () => void;
  onMute?: () => void;
}

function handlerName(action: string): keyof RemoteHandlers {
  return `on${action.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join("")}` as keyof RemoteHandlers;
}

function actionHandlers(h: RemoteHandlers): RemoteActionHandlers {
  return Object.fromEntries(
    REMOTE_ACTIONS.map((action) => [action, h[handlerName(action)]]),
  );
}

export function useKioskRemote(getHandlers: () => RemoteHandlers, enabled = true) {
  const handlersRef = useRef(getHandlers);
  useEffect(() => {
    handlersRef.current = getHandlers;
  });

  useEffect(() => {
    if (!enabled) return;
    void loadRemoteBindings();

    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const action = pickHandler(actionHandlers(handlersRef.current()), keyBinding(currentRemoteBindings(), e.key, e.keyCode));
      if (action) {
        e.preventDefault();
        action();
      }
    };
    window.addEventListener("keydown", onKeyDown);

    let rafId: number | null = null;
    const lastTriggerRef: Record<string, number> = {};
    const AXIS_THRESHOLD = 0.5;
    const REPEAT_DELAY_MS = 350;
    const REPEAT_RATE_MS = 140;

    const pollGamepads = () => {
      let polling = false;
      if (typeof navigator !== "undefined" && typeof navigator.getGamepads === "function") {
        const gamepads = navigator.getGamepads();
        const now = Date.now();
        const h = actionHandlers(handlersRef.current());

        for (let i = 0; i < gamepads.length; i++) {
          const gp = gamepads[i];
          if (!gp || !gp.connected) continue;
          polling = true;

          const checkAction = (key: string, isPressed: boolean, action?: () => void, isDirectional = false) => {
            if (!action) return;
            const lastTime = lastTriggerRef[key] || 0;
            if (isPressed) {
              if (lastTime === 0) {
                lastTriggerRef[key] = now;
                action();
              } else if (isDirectional) {
                const elapsed = now - lastTime;
                if (elapsed >= REPEAT_DELAY_MS) {
                  const step = Math.floor((elapsed - REPEAT_DELAY_MS) / REPEAT_RATE_MS);
                  const lastStep = lastTriggerRef[`${key}_step`] || 0;
                  if (step > lastStep) {
                    lastTriggerRef[`${key}_step`] = step;
                    action();
                  }
                }
              }
            } else {
              delete lastTriggerRef[key];
              delete lastTriggerRef[`${key}_step`];
            }
          };

          const axes: Record<number, boolean> = {
            12: gp.axes[1] !== undefined && gp.axes[1] < -AXIS_THRESHOLD,
            13: gp.axes[1] !== undefined && gp.axes[1] > AXIS_THRESHOLD,
            14: gp.axes[0] !== undefined && gp.axes[0] < -AXIS_THRESHOLD,
            15: gp.axes[0] !== undefined && gp.axes[0] > AXIS_THRESHOLD,
          };
          for (const [button, actions] of gamepadBindings(currentRemoteBindings())) {
            const analog = (ANALOG_TRIGGERS as readonly number[]).includes(button) && (gp.buttons[button]?.value ?? 0) > 0.5;
            const pressed = (gp.buttons[button]?.pressed ?? false) || analog || (axes[button] ?? false);
            checkAction(`gp_${i}_${button}`, pressed, pickHandler(h, actions), button in GAMEPAD_DIRECTIONS);
          }
        }
      }
      rafId = polling ? requestAnimationFrame(pollGamepads) : null;
    };

    const startPolling = () => {
      if (rafId === null) rafId = requestAnimationFrame(pollGamepads);
    };
    window.addEventListener("gamepadconnected", startPolling);
    startPolling();

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("gamepadconnected", startPolling);
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [enabled]);
}

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
