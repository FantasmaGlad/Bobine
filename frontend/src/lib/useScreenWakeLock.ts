"use client";

import { useEffect, useRef } from "react";

/**
 * Maintien de l'écran allumé (Anti-veille / Screen Wake Lock API).
 *
 * Sur les profils d'application de bureau (Windows, macOS, Linux desktop),
 * les sorties vidéo et audio (/cinema, /kiosk, /coach, /radio) peuvent être
 * consultées directement dans un onglet ou une fenêtre du navigateur par défaut,
 * en dehors du mode kiosque natif supervisé par BobineTray.
 *
 * Ce hook demande un verrou d'écran ("screen wake lock") dès que la route plein écran
 * est active, le redemande quand l'onglet redevient visible ou quand le système le retire,
 * et le libère lors de la navigation vers une page d'administration ou au démontage.
 */
const WAKE_LOCK_RETRY_MS = 15_000;

export function useScreenWakeLock(enabled: boolean) {
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    if (!enabled || typeof navigator === "undefined" || !("wakeLock" in navigator)) {
      return;
    }

    let isActive = true;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const retryLater = () => {
      if (!isActive || retryTimer) return;
      retryTimer = setTimeout(() => {
        retryTimer = null;
        requestWakeLock();
      }, WAKE_LOCK_RETRY_MS);
    };

    const requestWakeLock = async () => {
      try {
        if (document.visibilityState !== "visible") return;
        // Si un verrou valide est déjà actif, rien à faire
        if (wakeLockRef.current && !wakeLockRef.current.released) return;

        // Fonction détectée plus haut (`"wakeLock" in navigator`) : absente de Firefox < 126
        // et hors contexte sécurisé, sans conséquence — l'échec est silencieux.
        // eslint-disable-next-line compat/compat -- détectée par feature detection
        const sentinel = await navigator.wakeLock.request("screen");
        if (!isActive) {
          await sentinel.release();
          return;
        }

        wakeLockRef.current = sentinel;
        sentinel.addEventListener("release", () => {
          if (wakeLockRef.current === sentinel) {
            wakeLockRef.current = null;
          }
          // Le système peut retirer le verrou sans que l'onglet soit masqué (économie d'énergie, changement de
          // session) : aucun `visibilitychange` ne suivrait, l'écran de la salle finirait par s'éteindre.
          retryLater();
        });
      } catch {
        // Refus du navigateur ou batterie trop faible : nouvelle tentative plus tard.
        retryLater();
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        requestWakeLock();
      }
    };

    requestWakeLock();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      isActive = false;
      if (retryTimer) clearTimeout(retryTimer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (wakeLockRef.current) {
        wakeLockRef.current.release().catch(() => {});
        wakeLockRef.current = null;
      }
    };
  }, [enabled]);
}
