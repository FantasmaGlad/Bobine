"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Pas d'une pression de touche volume (télécommande, clavier, manette). */
export const VOLUME_STEP = 0.05;
/** Durée d'affichage de l'indicateur après la dernière action. */
export const VOLUME_HUD_MS = 1800;

export interface VolumeState {
  level: number;
  muted: boolean;
}

/** Niveau après un pas, borné à [0, 1] et arrondi au centième (évite la dérive des flottants). */
export function stepVolume(level: number, delta: number): number {
  return Math.max(0, Math.min(1, Math.round((level + delta) * 100) / 100));
}

type MediaVolume = Pick<HTMLMediaElement, "volume" | "muted">;

/**
 * Règle le volume de tous les éléments d'un même lecteur (ex. les deux platines A/B, vidéo + audio).
 * Part de l'état du premier élément ; `delta` change le niveau, `toggleMute` bascule la sourdine.
 * Un niveau à 0 vaut sourdine ; remonter le niveau la lève.
 */
export function adjustMediaVolume(elements: Array<MediaVolume | null | undefined>, delta: number, toggleMute = false): VolumeState {
  const present = elements.filter((el): el is MediaVolume => Boolean(el));
  const reference = present[0];
  const level = reference ? reference.volume : 1;
  const muted = reference ? reference.muted : false;
  const next: VolumeState = toggleMute
    ? { level, muted: !muted }
    : { level: stepVolume(level, delta), muted: stepVolume(level, delta) === 0 };
  for (const el of present) {
    el.volume = next.level;
    el.muted = next.muted;
  }
  return next;
}

/** État de l'indicateur de volume + minuterie de masquage. */
export function useVolumeHud(duration = VOLUME_HUD_MS) {
  const [hud, setHud] = useState<VolumeState & { visible: boolean }>({ visible: false, level: 1, muted: false });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const show = useCallback(
    (state: VolumeState) => {
      setHud({ visible: true, ...state });
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setHud((prev) => ({ ...prev, visible: false })), duration);
    },
    [duration],
  );
  return [hud, show] as const;
}
