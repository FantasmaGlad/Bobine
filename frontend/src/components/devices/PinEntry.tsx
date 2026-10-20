"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { appendDigit, deleteDigit, emptyPin, isComplete, keyToAction, type PinBuffer } from "@/lib/pinEntry";

export type PinStatus = "idle" | "error" | "success" | "locked";

interface PinEntryProps {
  length: number;
  /** Appelé avec le code complet, après un court délai (laisse la dernière bulle se remplir). */
  onComplete: (pin: string) => void;
  status?: PinStatus;
  caption?: string;
  /** Incrémenter pour vider la saisie (après une erreur, au changement de phase). */
  resetKey?: number;
  disabled?: boolean;
  /** Libellés d'accessibilité. */
  labels: { group: string; delete: string; filled: (count: number, total: number) => string };
}

const PAD_ROWS = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]];

/** Six bulles + pavé numérique en verre ; clavier physique et télécommande acceptés. */
export default function PinEntry({ length, onComplete, status = "idle", caption, resetKey = 0, disabled = false, labels }: PinEntryProps) {
  const [buffer, setBuffer] = useState<PinBuffer>(() => emptyPin(length));
  const locked = disabled || status === "locked" || status === "success";

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- remise à zéro demandée par le parent (erreur, changement de phase)
    setBuffer(emptyPin(length));
  }, [resetKey, length]);

  useEffect(() => {
    if (!isComplete(buffer)) return;
    const timer = setTimeout(() => onComplete(buffer.digits), 140);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seule la complétion de la saisie déclenche l'envoi
  }, [buffer.digits]);

  const press = useCallback((digit: string) => {
    if (locked) return;
    // Retour haptique léger quand l'appareil en a un (détection de fonctionnalité).
    const vibrate = (navigator as { vibrate?: (pattern: number) => boolean }).vibrate;
    try { vibrate?.call(navigator, 8); } catch { /* sans vibreur */ }
    setBuffer((b) => appendDigit(b, digit));
  }, [locked]);
  const erase = useCallback(() => { if (!locked) setBuffer((b) => deleteDigit(b)); }, [locked]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const action = keyToAction(event.key);
      if (!action) return;
      event.preventDefault();
      if (action.type === "digit") press(action.digit);
      else erase();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [press, erase]);

  const count = buffer.digits.length;
  return (
    <div className={`pin-entry pin-${status}`}>
      <div className="pin-dots" role="group" aria-label={labels.group}>
        {Array.from({ length }, (_, i) => (
          <span key={i} className={`pin-dot ${i < count ? "filled" : ""} ${i === count && status === "idle" ? "next" : ""}`} />
        ))}
      </div>
      <span className="sr-only" aria-live="polite">{labels.filled(count, length)}</span>
      <p className={`pin-caption ${status === "error" ? "is-error" : ""}`} aria-live="polite">{caption ?? " "}</p>
      <div className="pin-pad" role="group">
        {PAD_ROWS.flat().map((digit) => (
          <button key={digit} type="button" className="pin-key" disabled={locked} onClick={() => press(digit)}>{digit}</button>
        ))}
        <span />
        <button type="button" className="pin-key" disabled={locked} onClick={() => press("0")}>0</button>
        <button type="button" className="pin-key pin-key--icon" disabled={locked || count === 0} onClick={erase} aria-label={labels.delete}>
          <Icon name="backspace" size={22} />
        </button>
      </div>
    </div>
  );
}
