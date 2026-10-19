import { test } from "node:test";
import assert from "node:assert/strict";
import { pickEntryPoint, pickNeighbor, type Box } from "../src/lib/spatialNav.ts";

const box = (left: number, top: number, w = 100, h = 40): Box => ({ left, top, right: left + w, bottom: top + h });

// Grille 3 colonnes x 2 rangées
const grid = [box(0, 0), box(120, 0), box(240, 0), box(0, 60), box(120, 60), box(240, 60)];

test("grille : droite et gauche restent dans la rangée", () => {
  assert.equal(pickNeighbor(grid[0], grid, "right"), 1);
  assert.equal(pickNeighbor(grid[1], grid, "right"), 2);
  assert.equal(pickNeighbor(grid[4], grid, "left"), 3);
  assert.equal(pickNeighbor(grid[5], grid, "right"), -1);
});

test("grille : haut et bas restent dans la colonne", () => {
  assert.equal(pickNeighbor(grid[1], grid, "down"), 4);
  assert.equal(pickNeighbor(grid[4], grid, "up"), 1);
  assert.equal(pickNeighbor(grid[0], grid, "up"), -1);
  assert.equal(pickNeighbor(grid[3], grid, "down"), -1);
});

test("un élément qui ne recouvre pas la rangée n'est choisi qu'à défaut d'autre", () => {
  const a = box(0, 0), sameRow = box(300, 0), otherRow = box(110, 200);
  assert.equal(pickNeighbor(a, [a, sameRow, otherRow], "right"), 1);
  // Sans voisin dans la rangée, l'élément d'une autre rangée est tout de même atteignable.
  assert.equal(pickNeighbor(a, [a, otherRow], "right"), 1);
});

test("barre d'outils et colonne latérale : le plus proche l'emporte", () => {
  const cur = box(200, 100);
  const near = box(320, 100), far = box(600, 100), sidebar = box(0, 100, 150);
  assert.equal(pickNeighbor(cur, [cur, far, near, sidebar], "right"), 2);
  assert.equal(pickNeighbor(cur, [cur, far, near, sidebar], "left"), 3);
});

test("éléments décalés de rangée : le plus aligné gagne", () => {
  const cur = box(0, 100);
  const aligned = box(200, 105), lower = box(150, 180);
  assert.equal(pickNeighbor(cur, [cur, lower, aligned], "right"), 2);
});

test("aucun candidat ou seul l'élément courant : -1", () => {
  assert.equal(pickNeighbor(grid[0], [], "down"), -1);
  assert.equal(pickNeighbor(grid[0], [grid[0]], "down"), -1);
});

test("un grand élément qui chevauche l'axe principal reste atteignable s'il est devant", () => {
  const cur = box(0, 0, 100, 40);
  const tall = box(50, 20, 100, 300); // commence avant la fin de cur, centre bien plus bas
  assert.equal(pickNeighbor(cur, [cur, tall], "down"), 1);
  const behind = box(0, -300, 100, 310); // déborde sur cur mais centre au-dessus
  assert.equal(pickNeighbor(cur, [cur, behind], "down"), -1);
});

test("point d'entrée : l'élément le plus proche du coin haut-gauche", () => {
  assert.equal(pickEntryPoint(grid), 0);
  assert.equal(pickEntryPoint([box(300, 300), box(10, 400), box(500, 10)]), 2);
  assert.equal(pickEntryPoint([]), -1);
});
