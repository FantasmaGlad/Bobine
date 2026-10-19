/**
 * Navigation spatiale au D-pad (télécommande, clavier, manette) — logique PURE, sans DOM, testable
 * (`frontend/tests/`). Le hook `useDpadNavigation` l'applique à tous les écrans d'administration.
 *
 * Principe : parmi les éléments situés dans la direction demandée, on retient le plus proche, en
 * privilégiant ceux qui se recouvrent sur l'axe transverse (même rangée / même colonne) — ce qui donne
 * le comportement attendu dans une grille (haut/bas reste dans la colonne) comme dans une barre
 * d'outils (gauche/droite reste dans la rangée).
 */

export type Direction = "left" | "right" | "up" | "down";

export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

const EDGE_TOLERANCE = 2;
/** Pénalité (px) d'un élément qui ne recouvre pas la rangée/colonne de l'élément courant. */
const NO_OVERLAP_PENALTY = 1000;

function overlap(aStart: number, aEnd: number, bStart: number, bEnd: number): number {
  return Math.max(0, Math.min(aEnd, bEnd) - Math.max(aStart, bStart));
}

/**
 * Index du meilleur voisin de `from` dans `direction` parmi `candidates`, ou -1 s'il n'y en a aucun.
 * `from` lui-même, s'il figure dans la liste (même boîte), n'est jamais retenu.
 */
export function pickNeighbor(from: Box, candidates: readonly Box[], direction: Direction): number {
  const horizontal = direction === "left" || direction === "right";
  let best = -1;
  let bestScore = Infinity;

  candidates.forEach((box, index) => {
    if (box === from) return;
    // Écart sur l'axe principal : bord de départ -> bord d'arrivée (négatif = chevauchement des axes).
    let gap: number;
    if (direction === "right") gap = box.left - from.right;
    else if (direction === "left") gap = from.left - box.right;
    else if (direction === "down") gap = box.top - from.bottom;
    else gap = from.top - box.bottom;
    if (gap < -EDGE_TOLERANCE) {
      // Éléments qui débordent : acceptés seulement s'ils sont réellement au-delà du CENTRE courant.
      const fromCenter = horizontal ? (from.left + from.right) / 2 : (from.top + from.bottom) / 2;
      const boxCenter = horizontal ? (box.left + box.right) / 2 : (box.top + box.bottom) / 2;
      const ahead = direction === "right" || direction === "down" ? boxCenter > fromCenter + EDGE_TOLERANCE : boxCenter < fromCenter - EDGE_TOLERANCE;
      if (!ahead) return;
      gap = 0;
    }
    const crossOverlap = horizontal
      ? overlap(from.top, from.bottom, box.top, box.bottom)
      : overlap(from.left, from.right, box.left, box.right);
    const fromCross = horizontal ? (from.top + from.bottom) / 2 : (from.left + from.right) / 2;
    const boxCross = horizontal ? (box.top + box.bottom) / 2 : (box.left + box.right) / 2;
    const crossDistance = Math.abs(boxCross - fromCross);
    const score = Math.max(0, gap) + crossDistance * 2 + (crossOverlap > 0 ? 0 : NO_OVERLAP_PENALTY);
    if (score < bestScore) {
      bestScore = score;
      best = index;
    }
  });
  return best;
}

/** Index du candidat le plus proche du coin haut-gauche (point d'entrée quand rien n'a le focus). */
export function pickEntryPoint(candidates: readonly Box[]): number {
  let best = -1;
  let bestScore = Infinity;
  candidates.forEach((box, index) => {
    const score = box.top * 2 + box.left;
    if (score < bestScore) {
      bestScore = score;
      best = index;
    }
  });
  return best;
}
