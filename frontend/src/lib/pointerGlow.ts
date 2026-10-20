/**
 * Halo qui suit le pointeur sur les éléments `.glass-interactive` — logique PURE (testable).
 * Le halo n'existe que pour une souris précise : jamais au toucher, à la télécommande, en mode
 * sobre (TV, Wyse) ni quand l'utilisateur demande moins de mouvement.
 */

export interface GlowEnvironment {
  /** `(hover: hover) and (pointer: fine)` */
  finePointer: boolean;
  /** `prefers-reduced-motion: reduce` */
  reducedMotion: boolean;
  /** `data-input-mode="remote"` posé par la navigation à la télécommande */
  remoteMode: boolean;
}

export function shouldGlow(env: GlowEnvironment): boolean {
  return env.finePointer && !env.reducedMotion && !env.remoteMode;
}

/** Position du pointeur relative à un rectangle, bornée à celui-ci (pixels). */
export function relativePosition(
  rect: { left: number; top: number; width: number; height: number },
  clientX: number,
  clientY: number,
): { x: number; y: number } {
  const x = Math.min(rect.width, Math.max(0, clientX - rect.left));
  const y = Math.min(rect.height, Math.max(0, clientY - rect.top));
  return { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10 };
}
