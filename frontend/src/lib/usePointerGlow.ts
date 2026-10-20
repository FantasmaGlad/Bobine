"use client";

import { useEffect } from "react";
import { relativePosition, shouldGlow } from "./pointerGlow";

function readEnvironment() {
  return {
    finePointer: window.matchMedia("(hover: hover) and (pointer: fine)").matches,
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    remoteMode: document.documentElement.getAttribute("data-input-mode") === "remote",
  };
}

/**
 * Pose `--mx` / `--my` (pixels) sur l'élément `.glass-interactive` survolé du conteneur. Un SEUL écouteur
 * délégué, limité à une mise à jour par image : coût négligeable même sur matériel modeste.
 */
export function usePointerGlow(containerRef: React.RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let frame = 0;
    let pending: { target: HTMLElement; x: number; y: number } | null = null;

    const flush = () => {
      frame = 0;
      if (!pending) return;
      pending.target.style.setProperty("--mx", `${pending.x}px`);
      pending.target.style.setProperty("--my", `${pending.y}px`);
      pending = null;
    };

    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== "mouse" || !shouldGlow(readEnvironment())) return;
      const target = (event.target as HTMLElement | null)?.closest<HTMLElement>(".glass-interactive");
      if (!target) return;
      const { x, y } = relativePosition(target.getBoundingClientRect(), event.clientX, event.clientY);
      pending = { target, x, y };
      if (!frame) frame = requestAnimationFrame(flush);
    };

    container.addEventListener("pointermove", onMove);
    return () => {
      container.removeEventListener("pointermove", onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [containerRef]);
}
