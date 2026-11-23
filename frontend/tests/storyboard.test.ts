import { test } from "node:test";
import assert from "node:assert/strict";
import { tileAt, type Storyboard } from "../src/lib/storyboard.ts";

const board: Storyboard = { url: "/x.jpg", interval_seconds: 14, count: 231, columns: 10, rows: 24, tile_width: 160, tile_height: 90 };

test("la vignette suit la position, ligne par ligne", () => {
  assert.deepEqual(tileAt(board, 0), { x: 0, y: 0 });
  assert.deepEqual(tileAt(board, 13.9), { x: 0, y: 0 });
  assert.deepEqual(tileAt(board, 14), { x: 160, y: 0 });
  assert.deepEqual(tileAt(board, 14 * 10), { x: 0, y: 90 });
  assert.deepEqual(tileAt(board, 14 * 23), { x: 480, y: 180 });
});

test("la vignette reste dans la mosaïque aux extrémités", () => {
  assert.deepEqual(tileAt(board, -5), { x: 0, y: 0 });
  assert.deepEqual(tileAt(board, 99999), { x: 0, y: 23 * 90 });
});
