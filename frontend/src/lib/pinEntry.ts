/**
 * Saisie du PIN en bulles — logique PURE (testable, `frontend/tests/`).
 * Aucune valeur n'est conservée au-delà du tampon de saisie en mémoire.
 */

export interface PinBuffer {
  digits: string;
  length: number;
}

export function emptyPin(length = 6): PinBuffer {
  return { digits: "", length };
}

export function appendDigit(buffer: PinBuffer, key: string): PinBuffer {
  if (!/^\d$/.test(key) || buffer.digits.length >= buffer.length) return buffer;
  return { ...buffer, digits: buffer.digits + key };
}

export function deleteDigit(buffer: PinBuffer): PinBuffer {
  return buffer.digits ? { ...buffer, digits: buffer.digits.slice(0, -1) } : buffer;
}

export function isComplete(buffer: PinBuffer): boolean {
  return buffer.digits.length === buffer.length;
}

/** Touche physique → action (chiffre ou retour arrière), null sinon. */
export function keyToAction(key: string): { type: "digit"; digit: string } | { type: "delete" } | null {
  if (/^\d$/.test(key)) return { type: "digit", digit: key };
  if (key === "Backspace" || key === "Delete") return { type: "delete" };
  return null;
}

// ---------------------------------------------------------------------------
// Définition du PIN en deux temps : « Nouveau code » puis « Confirmez le code »
// ---------------------------------------------------------------------------

export type SetPhase = "new" | "confirm";

export interface SetFlow {
  phase: SetPhase;
  /** Premier code saisi (gardé en mémoire le temps de la confirmation). */
  first: string;
  /** Vrai juste après une confirmation différente du premier code. */
  mismatch: boolean;
}

export const initialSetFlow: SetFlow = { phase: "new", first: "", mismatch: false };

export type SetResult =
  | { kind: "next"; flow: SetFlow }
  | { kind: "mismatch"; flow: SetFlow }
  | { kind: "done"; pin: string; flow: SetFlow };

/** Un code complet vient d'être saisi : passe à la confirmation, signale l'écart ou termine. */
export function submitSetCode(flow: SetFlow, code: string): SetResult {
  if (flow.phase === "new") {
    return { kind: "next", flow: { phase: "confirm", first: code, mismatch: false } };
  }
  if (code === flow.first) return { kind: "done", pin: code, flow: initialSetFlow };
  return { kind: "mismatch", flow: { phase: "new", first: "", mismatch: true } };
}
