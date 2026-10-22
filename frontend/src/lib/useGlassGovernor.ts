"use client";

import { useEffect } from "react";
import { applyScale, loadMode, loadStep, MIN_SAMPLE, MODE_EVENT, nextStep, saveStep, scaleForMode } from "./glassQuality";

/** Applique la qualité du verre et, en mode auto, la réduit si le défilement saccade (voir glassQuality.ts). */
export function useGlassGovernor(): void {
  useEffect(() => {
    let step = loadStep();
    let stopGovernor = () => {};

    const start = () => {
      stopGovernor();
      stopGovernor = () => {};
      const mode = loadMode();
      applyScale(scaleForMode(mode, step));
      if (mode !== "auto" || step >= 2) return;

      // Durées d'image relevées uniquement pendant un défilement (c'est là que le flou coûte).
      let deltas: number[] = [];
      let lastScrollAt = 0;
      let last = 0;
      let raf = 0;
      const onScroll = () => {
        lastScrollAt = performance.now();
        if (!raf) raf = requestAnimationFrame(tick);
      };
      const tick = (now: number) => {
        raf = 0;
        if (document.hidden || now - lastScrollAt > 150) { last = 0; return; }
        if (last) deltas.push(now - last);
        last = now;
        if (deltas.length >= MIN_SAMPLE) {
          const next = nextStep(deltas, step);
          deltas = [];
          if (next !== step) {
            step = next;
            saveStep(step);
            applyScale(scaleForMode("auto", step));
            if (step >= 2) { stopGovernor(); return; }
          }
        }
        raf = requestAnimationFrame(tick);
      };
      window.addEventListener("scroll", onScroll, { capture: true, passive: true });
      stopGovernor = () => {
        window.removeEventListener("scroll", onScroll, { capture: true });
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
      };
    };

    start();
    window.addEventListener(MODE_EVENT, start);
    return () => {
      window.removeEventListener(MODE_EVENT, start);
      stopGovernor();
    };
  }, []);
}
