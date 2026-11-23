import { test } from "node:test";
import assert from "node:assert/strict";
import { clampSeconds, entryDurationMs, moved, nextIndex, type SignageEntry } from "../src/lib/signageLoop.ts";

const entry = (play_seconds: number | null): SignageEntry => ({
  background_id: 1, seconds: play_seconds, title: "Affiche", is_image: play_seconds !== null, play_seconds, duration_seconds: null,
});

test("une image dure son nombre de secondes, une vidéo entière attend sa fin", () => {
  assert.equal(entryDurationMs(entry(12)), 12000);
  assert.equal(entryDurationMs(entry(null)), null);
});

test("la boucle repart du début après le dernier visuel", () => {
  assert.deepEqual([0, 1, 2].map((i) => nextIndex(i, 3)), [1, 2, 0]);
  assert.equal(nextIndex(0, 0), 0);
});

test("déplacer un visuel garde les autres dans l'ordre, sans sortir de la liste", () => {
  assert.deepEqual(moved(["a", "b", "c"], 0, 1), ["b", "a", "c"]);
  assert.deepEqual(moved(["a", "b", "c"], 2, 0), ["c", "a", "b"]);
  assert.deepEqual(moved(["a", "b"], 0, -1), ["a", "b"]);
  assert.deepEqual(moved(["a", "b"], 1, 2), ["a", "b"]);
});

test("une durée saisie est bornée de 2 s à 1 h ; vide : durée par défaut", () => {
  assert.deepEqual(["", "1", "7.6", "99999", "abc"].map(clampSeconds), [null, 2, 8, 3600, null]);
});
