import { test } from "node:test";
import assert from "node:assert/strict";
import { tileAt, type Storyboard } from "../src/lib/storyboard.ts";

const board: Storyboard = { sheets: ["/0.jpg", "/1.jpg", "/2.jpg"], interval_seconds: 14, count: 231, columns: 10, rows: 10, tile_width: 320, tile_height: 180 };

test("la vignette suit la position, ligne par ligne puis planche par planche", () => {
  assert.deepEqual(tileAt(board, 0), { sheet: 0, x: 0, y: 0 });
  assert.deepEqual(tileAt(board, 14), { sheet: 0, x: 320, y: 0 });
  assert.deepEqual(tileAt(board, 14 * 10), { sheet: 0, x: 0, y: 180 });
  assert.deepEqual(tileAt(board, 14 * 99), { sheet: 0, x: 2880, y: 1620 });
  assert.deepEqual(tileAt(board, 14 * 100), { sheet: 1, x: 0, y: 0 });
});

test("la vignette reste dans les planches aux extrémités", () => {
  assert.deepEqual(tileAt(board, -5), { sheet: 0, x: 0, y: 0 });
  assert.deepEqual(tileAt(board, 99999), { sheet: 2, x: 0, y: 540 });
});
