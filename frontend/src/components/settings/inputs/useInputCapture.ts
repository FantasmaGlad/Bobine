"use client";

import { useEffect } from "react";
import { pressedButton, sourceFromKey } from "@/lib/inputSource";

function buttonStates(): boolean[] {
  const pads = typeof navigator.getGamepads === "function" ? navigator.getGamepads() : [];
  const states: boolean[] = [];
  for (const pad of pads) pad?.buttons.forEach((button, index) => { states[index] = states[index] || button.pressed; });
  return states;
}

export function useInputCapture(active: boolean, onCapture: (source: string) => void) {
  useEffect(() => {
    if (!active) return;
    const onKeyDown = (event: KeyboardEvent) => {
      event.preventDefault();
      event.stopPropagation();
      onCapture(sourceFromKey(event.key, event.keyCode));
    };
    window.addEventListener("keydown", onKeyDown, { capture: true });
    let previous = buttonStates();
    let frame = requestAnimationFrame(function poll() {
      const current = buttonStates();
      const button = pressedButton(previous, current);
      previous = current;
      if (button !== null) onCapture(`pad:${button}`);
      else frame = requestAnimationFrame(poll);
    });
    return () => {
      window.removeEventListener("keydown", onKeyDown, { capture: true });
      cancelAnimationFrame(frame);
    };
  }, [active, onCapture]);
}
