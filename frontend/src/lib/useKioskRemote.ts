"use client";

import { useEffect, useRef } from "react";

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

const ANDROID_TV_KEYCODES: Partial<Record<number, keyof RemoteHandlers>> = {
  4: "onBack",
  19: "onUp",
  20: "onDown",
  21: "onLeft",
  22: "onRight",
  23: "onEnter",
  66: "onEnter",
  24: "onVolumeUp",
  25: "onVolumeDown",
  164: "onMute",
  85: "onPlayPause",
  126: "onPlayPause",
  127: "onPlayPause",
  87: "onNext",
  88: "onPrev",
  166: "onChapterNext",
  167: "onChapterPrev",
};

export function useKioskRemote(getHandlers: () => RemoteHandlers, enabled = true) {
  const handlersRef = useRef(getHandlers);
  useEffect(() => {
    handlersRef.current = getHandlers;
  });

  useEffect(() => {
    if (!enabled) return;

    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const h = handlersRef.current();
      let action: (() => void) | undefined;
      switch (e.key) {
        case "ArrowLeft": action = h.onLeft; break;
        case "ArrowRight": action = h.onRight; break;
        case "ArrowUp": action = h.onUp; break;
        case "ArrowDown": action = h.onDown; break;
        case "Enter":
        case "Select":
        case "Ok": action = h.onEnter; break;
        case "Escape":
        case "Backspace":
        case "BrowserBack":
        case "GoBack":
        case "Back": action = h.onBack; break;
        case " ":
        case "Spacebar": action = h.onPlayPause ?? h.onEnter; break;
        case "MediaPlayPause":
        case "MediaPlay":
        case "MediaPause":
        case "Play":
        case "Pause": action = h.onPlayPause; break;
        case "MediaTrackNext":
        case "FastForward":
        case "MediaFastForward": action = h.onNext; break;
        case "MediaTrackPrevious":
        case "Rewind":
        case "MediaRewind": action = h.onPrev; break;
        case "ChannelUp": action = h.onChapterNext ?? h.onNext; break;
        case "ChannelDown": action = h.onChapterPrev ?? h.onPrev; break;
        case "PageDown": action = h.onNext ?? h.onDown; break;
        case "PageUp": action = h.onPrev ?? h.onUp; break;
        case "MediaStop": action = h.onBack; break;
        case "AudioVolumeUp":
        case "VolumeUp": action = h.onVolumeUp; break;
        case "AudioVolumeDown":
        case "VolumeDown": action = h.onVolumeDown; break;
        case "AudioVolumeMute":
        case "VolumeMute": action = h.onMute; break;
        default: {
          const mapped = ANDROID_TV_KEYCODES[e.keyCode];
          if (!mapped) return;
          action = mapped === "onChapterNext" ? (h.onChapterNext ?? h.onNext)
            : mapped === "onChapterPrev" ? (h.onChapterPrev ?? h.onPrev)
            : h[mapped];
          break;
        }
      }
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
      if (typeof navigator !== "undefined" && typeof navigator.getGamepads === "function") {
        const gamepads = navigator.getGamepads();
        const now = Date.now();
        const h = handlersRef.current();

        for (let i = 0; i < gamepads.length; i++) {
          const gp = gamepads[i];
          if (!gp || !gp.connected) continue;

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

          const dpadUp = (gp.buttons[12]?.pressed ?? false) || (gp.axes[1] !== undefined && gp.axes[1] < -AXIS_THRESHOLD);
          const dpadDown = (gp.buttons[13]?.pressed ?? false) || (gp.axes[1] !== undefined && gp.axes[1] > AXIS_THRESHOLD);
          const dpadLeft = (gp.buttons[14]?.pressed ?? false) || (gp.axes[0] !== undefined && gp.axes[0] < -AXIS_THRESHOLD);
          const dpadRight = (gp.buttons[15]?.pressed ?? false) || (gp.axes[0] !== undefined && gp.axes[0] > AXIS_THRESHOLD);

          checkAction(`gp_${i}_up`, dpadUp, h.onUp, true);
          checkAction(`gp_${i}_down`, dpadDown, h.onDown, true);
          checkAction(`gp_${i}_left`, dpadLeft, h.onLeft, true);
          checkAction(`gp_${i}_right`, dpadRight, h.onRight, true);

          const btnA = gp.buttons[0]?.pressed ?? false;
          checkAction(`gp_${i}_btnA`, btnA, h.onEnter ?? h.onPlayPause);

          const btnB = gp.buttons[1]?.pressed ?? false;
          checkAction(`gp_${i}_btnB`, btnB, h.onBack);

          const btnX = gp.buttons[2]?.pressed ?? false;
          checkAction(`gp_${i}_btnX`, btnX, h.onPlayPause);

          const btnY = gp.buttons[3]?.pressed ?? false;
          checkAction(`gp_${i}_btnY`, btnY, h.onPlayPause);

          const btnL1 = gp.buttons[4]?.pressed ?? false;
          const btnR1 = gp.buttons[5]?.pressed ?? false;
          checkAction(`gp_${i}_btnL1`, btnL1, h.onPrev);
          checkAction(`gp_${i}_btnR1`, btnR1, h.onNext);

          const btnL2 = (gp.buttons[6]?.pressed ?? false) || ((gp.buttons[6]?.value ?? 0) > 0.5);
          const btnR2 = (gp.buttons[7]?.pressed ?? false) || ((gp.buttons[7]?.value ?? 0) > 0.5);
          checkAction(`gp_${i}_btnL2`, btnL2, h.onVolumeDown);
          checkAction(`gp_${i}_btnR2`, btnR2, h.onVolumeUp);

          const btnSelect = gp.buttons[8]?.pressed ?? false;
          const btnStart = gp.buttons[9]?.pressed ?? false;
          checkAction(`gp_${i}_btnSelect`, btnSelect, h.onBack);
          checkAction(`gp_${i}_btnStart`, btnStart, h.onPlayPause);
        }
      }
      rafId = requestAnimationFrame(pollGamepads);
    };

    rafId = requestAnimationFrame(pollGamepads);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
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
    window.scrollTo({ top: 0, behavior: "smooth" });
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

  const targetEl =
    bestItem ??
    items[
      (currentIndex + (direction === "right" || direction === "down" ? 1 : -1) + items.length) % items.length
    ];

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
