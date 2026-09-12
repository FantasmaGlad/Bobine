"use client";

import { useEffect, useRef } from "react";

/**
 * Support UNIVERSEL des PÉRIPHÉRIQUES D'ENTRÉE :
 * 1. Télécommandes à dongle USB / Bluetooth (présentateur, télécommande multimédia, "air remote").
 * 2. Claviers physiques.
 * 3. Manettes de jeu USB et Bluetooth (Xbox, PlayStation, 8BitDo, Switch Pro, manettes génériques)
 *    via la HTML5 Gamepad API standardisée.
 * 4. Touches multimédia standard (Play, Pause, Next, Prev, Volume, Stop).
 *
 * `getHandlers` est relu à CHAQUE événement (via ref) pour toujours refléter l'état
 * courant sans réattacher inutilement l'écouteur.
 */
export interface RemoteHandlers {
  onLeft?: () => void;
  onRight?: () => void;
  onUp?: () => void;
  onDown?: () => void;
  /** OK / sélection (Entrée / Bouton A / Croix). */
  onEnter?: () => void;
  /** Retour (Échap / Backspace / touche retour / Bouton B / Rond). */
  onBack?: () => void;
  /** Espace, touche média Play/Pause ou bouton X / Y / Start. */
  onPlayPause?: () => void;
  /** Piste/élément suivant (média Next / Page↓ / R1). */
  onNext?: () => void;
  /** Piste/élément précédent (média Prev / Page↑ / L1). */
  onPrev?: () => void;
  onVolumeUp?: () => void;
  onVolumeDown?: () => void;
  onMute?: () => void;
}

export function useKioskRemote(getHandlers: () => RemoteHandlers, enabled = true) {
  const handlersRef = useRef(getHandlers);
  handlersRef.current = getHandlers;

  useEffect(() => {
    if (!enabled) return;

    // --- 1. Gestion des événements clavier & télécommandes HID ---
    const onKeyDown = (e: KeyboardEvent) => {
      // Ne jamais détourner les touches quand l'utilisateur tape dans un champ de texte.
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
        case "GoBack": action = h.onBack; break;
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
        case "PageDown": action = h.onNext ?? h.onDown; break;
        case "PageUp": action = h.onPrev ?? h.onUp; break;
        case "MediaStop": action = h.onBack; break;
        case "AudioVolumeUp":
        case "VolumeUp": action = h.onVolumeUp; break;
        case "AudioVolumeDown":
        case "VolumeDown": action = h.onVolumeDown; break;
        case "AudioVolumeMute":
        case "VolumeMute": action = h.onMute; break;
        default: return;
      }
      if (action) {
        e.preventDefault();
        action();
      }
    };
    window.addEventListener("keydown", onKeyDown);

    // --- 2. Support Gamepad API (HTML5) avec polling lissé ---
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

          // Aide pour déclencher une action avec anti-rebond ou répétition
          const checkAction = (key: string, isPressed: boolean, action?: () => void, isDirectional = false) => {
            if (!action) return;
            const lastTime = lastTriggerRef[key] || 0;
            if (isPressed) {
              if (lastTime === 0) {
                // Premier appui franc
                lastTriggerRef[key] = now;
                action();
              } else if (isDirectional) {
                // Répétition fluide lors d'un maintien de direction
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
              // Bouton ou axe relâché
              delete lastTriggerRef[key];
              delete lastTriggerRef[`${key}_step`];
            }
          };

          // Croix directionnelle (D-Pad standard : 12=Haut, 13=Bas, 14=Gauche, 15=Droite)
          // et stick analogique gauche (axe 0=X, axe 1=Y)
          const dpadUp = (gp.buttons[12]?.pressed ?? false) || (gp.axes[1] !== undefined && gp.axes[1] < -AXIS_THRESHOLD);
          const dpadDown = (gp.buttons[13]?.pressed ?? false) || (gp.axes[1] !== undefined && gp.axes[1] > AXIS_THRESHOLD);
          const dpadLeft = (gp.buttons[14]?.pressed ?? false) || (gp.axes[0] !== undefined && gp.axes[0] < -AXIS_THRESHOLD);
          const dpadRight = (gp.buttons[15]?.pressed ?? false) || (gp.axes[0] !== undefined && gp.axes[0] > AXIS_THRESHOLD);

          checkAction(`gp_${i}_up`, dpadUp, h.onUp, true);
          checkAction(`gp_${i}_down`, dpadDown, h.onDown, true);
          checkAction(`gp_${i}_left`, dpadLeft, h.onLeft, true);
          checkAction(`gp_${i}_right`, dpadRight, h.onRight, true);

          // Bouton A / Croix (0) : Valider / Lancer / Play-Pause
          const btnA = gp.buttons[0]?.pressed ?? false;
          checkAction(`gp_${i}_btnA`, btnA, h.onEnter ?? h.onPlayPause);

          // Bouton B / Rond (1) : Retour
          const btnB = gp.buttons[1]?.pressed ?? false;
          checkAction(`gp_${i}_btnB`, btnB, h.onBack);

          // Bouton X / Carré (2) : Play / Pause
          const btnX = gp.buttons[2]?.pressed ?? false;
          checkAction(`gp_${i}_btnX`, btnX, h.onPlayPause);

          // Bouton Y / Triangle (3) : Play / Pause
          const btnY = gp.buttons[3]?.pressed ?? false;
          checkAction(`gp_${i}_btnY`, btnY, h.onPlayPause);

          // Gâchettes hautes L1 (4) / R1 (5) : Précédent / Suivant
          const btnL1 = gp.buttons[4]?.pressed ?? false;
          const btnR1 = gp.buttons[5]?.pressed ?? false;
          checkAction(`gp_${i}_btnL1`, btnL1, h.onPrev);
          checkAction(`gp_${i}_btnR1`, btnR1, h.onNext);

          // Gâchettes analogiques L2 (6) / R2 (7) : Volume Bas / Volume Haut
          const btnL2 = (gp.buttons[6]?.pressed ?? false) || ((gp.buttons[6]?.value ?? 0) > 0.5);
          const btnR2 = (gp.buttons[7]?.pressed ?? false) || ((gp.buttons[7]?.value ?? 0) > 0.5);
          checkAction(`gp_${i}_btnL2`, btnL2, h.onVolumeDown);
          checkAction(`gp_${i}_btnR2`, btnR2, h.onVolumeUp);

          // Select / Back (8) & Start / Options (9)
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

/** Classe posée par la télécommande ou la manette sur l'élément sélectionné. */
export const REMOTE_FOCUS_CLASS = "kiosk-remote-focus";

/**
 * Déplacement spatial bidirectionnel 2D (Haut / Bas / Gauche / Droite)
 * calculé à partir de la position visuelle géométrique des éléments dans le viewport.
 * Idéal pour naviguer fluidement dans les rangées et grilles de cours avec le D-Pad ou stick.
 */
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
    const el = items[0];
    for (const it of items) it.classList.toggle(REMOTE_FOCUS_CLASS, it === el);
    el.focus();
    el.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
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
      // Priorité à l'axe principal avec pondération sur l'axe transverse
      const score = mainDist + crossDist * 2.2;
      if (score < bestScore) {
        bestScore = score;
        bestItem = it;
      }
    }
  }

  // Si aucun voisin géométrique direct n'est trouvé dans cette direction,
  // repli propre sur l'ordre séquentiel du DOM
  const targetEl =
    bestItem ??
    items[
      (currentIndex + (direction === "right" || direction === "down" ? 1 : -1) + items.length) % items.length
    ];

  if (targetEl) {
    for (const it of items) it.classList.toggle(REMOTE_FOCUS_CLASS, it === targetEl);
    targetEl.focus();
    targetEl.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }
}

/**
 * Déplace la sélection séquentielle (1D) entre des éléments dans l'ordre du DOM.
 */
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
  const el = items[next];
  for (const it of items) it.classList.toggle(REMOTE_FOCUS_CLASS, it === el);
  el.focus();
  el.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
}

/**
 * Active (clique) l'élément sélectionné par la télécommande ou manette, ou le premier à défaut.
 */
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
