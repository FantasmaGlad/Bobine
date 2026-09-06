"use client";

import { useEffect, useRef } from "react";

/**
 * Maintien de l'écran allumé (Anti-veille / Screen Wake Lock API).
 *
 * Réf. Chantier Transverse C (§6 du plan de portabilité multi-OS) :
 * Sur les profils d'application de bureau (Windows, macOS, Linux desktop),
 * les sorties vidéo et audio (/cinema, /kiosk, /coach, /radio) peuvent être
 * consultées directement dans un onglet ou une fenêtre du navigateur par défaut,
 * en dehors du mode kiosque natif supervisé par BobineTray.
 *
 * Ce hook demande un verrou d'écran ("screen wake lock") dès que la route plein écran
 * est active, le réacquiert automatiquement lorsque l'onglet redevient visible après
 * avoir été masqué, et le libère proprement lors de la navigation vers une page standard
 * d'administration ou lors du démontage du composant.
 */
export function useScreenWakeLock(enabled: boolean) {
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    if (!enabled || typeof navigator === "undefined" || !("wakeLock" in navigator)) {
      return;
    }

    let isActive = true;

    const requestWakeLock = async () => {
      try {
        if (document.visibilityState !== "visible") return;
        // Si un verrou valide est déjà actif, rien à faire
        if (wakeLockRef.current && !wakeLockRef.current.released) return;

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
        });
      } catch {
        // Échec silencieux si refusé par la politique du navigateur ou si la batterie est trop faible
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
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (wakeLockRef.current) {
        wakeLockRef.current.release().catch(() => {});
        wakeLockRef.current = null;
      }
    };
  }, [enabled]);
}
