"use client";

import { useEffect } from "react";
import { applyScale, loadMode, loadStep, MIN_SAMPLE, MODE_EVENT, nextStep, saveStep, scaleForMode } from "./glassQuality";

/** Durée pendant laquelle une activité (défilement, touche, transition) fait mesurer les images. */
const ACTIVITY_WINDOW_MS = 250;

/** Applique la qualité du verre et, en mode auto, la réduit si l'interface saccade pendant l'activité (voir glassQuality.ts). */
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

      // Durées d'image relevées pendant l'activité qui coûte du flou : défilement, mais aussi navigation à la
      // télécommande ou au doigt, ouverture de feuilles et transitions (sur une télévision, on défile peu).
      let deltas: number[] = [];
      let lastActivityAt = 0;
      let last = 0;
      let raf = 0;
      const onActivity = () => {
        lastActivityAt = performance.now();
        if (!raf) raf = requestAnimationFrame(tick);
      };
      const tick = (now: number) => {
        raf = 0;
        if (document.hidden || now - lastActivityAt > ACTIVITY_WINDOW_MS) { last = 0; return; }
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
      const events = ["scroll", "keydown", "pointerdown", "transitionrun"] as const;
      for (const name of events) window.addEventListener(name, onActivity, { capture: true, passive: true });
      stopGovernor = () => {
        for (const name of events) window.removeEventListener(name, onActivity, { capture: true });
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
