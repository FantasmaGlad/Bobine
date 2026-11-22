import { test } from "node:test";
import assert from "node:assert/strict";
import { edgeFallbackIndex, scrollContainerOf, type ScrollNode } from "../src/lib/scrollContainer.ts";

interface Node extends ScrollNode { name: string; overflow: string; parentElement: Node | null }
const node = (name: string, overflow: string, parent: Node | null, scrollHeight = 100, clientHeight = 100): Node =>
  ({ name, overflow, parentElement: parent, scrollHeight, clientHeight });

test("la couche qui défile vraiment est trouvée, pas la fenêtre", () => {
  const body = node("body", "visible", null, 900, 900);
  const layer = node("cinema-grid-layer", "auto", body, 3000, 900);
  const hero = node("cinema-hero", "visible", layer);
  const play = node("cinema-hero-play", "visible", hero);
  assert.equal(scrollContainerOf(play, (n) => n.overflow)?.name, "cinema-grid-layer");
});

test("un conteneur sans débordement ou non défilant est ignoré", () => {
  const root = node("root", "auto", null, 500, 500);
  const hidden = node("hidden", "hidden", root, 2000, 400);
  const item = node("item", "visible", hidden);
  assert.equal(scrollContainerOf(item, (n) => n.overflow), null);
});

test("aux extrémités, haut et bas gardent la sélection, gauche et droite bouclent", () => {
  assert.equal(edgeFallbackIndex(0, 5, "up"), 0);
  assert.equal(edgeFallbackIndex(4, 5, "down"), 4);
  assert.equal(edgeFallbackIndex(0, 5, "left"), 4);
  assert.equal(edgeFallbackIndex(4, 5, "right"), 0);
});
