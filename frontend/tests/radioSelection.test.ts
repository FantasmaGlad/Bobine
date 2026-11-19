import assert from "node:assert/strict";
import test from "node:test";

import { mergedIds, tagStateOf, toggledAll, toggledSet } from "../src/components/radio-library/selectionOps.ts";

test("cocher et décocher une piste ne touche pas l'ensemble d'origine", () => {
  const prev = new Set([1]);
  assert.deepEqual([...toggledSet(prev, 2)], [1, 2]);
  assert.deepEqual([...toggledSet(prev, 1)], []);
  assert.deepEqual([...prev], [1]);
});

test("tout cocher ajoute ce qui manque, tout décocher retire la page", () => {
  assert.deepEqual([...toggledAll(new Set([1]), [1, 2, 3], false)].sort(), [1, 2, 3]);
  assert.deepEqual([...toggledAll(new Set([1, 2, 9]), [1, 2], true)], [9]);
});

test("l'état d'une étiquette sur la sélection", () => {
  assert.equal(tagStateOf([], "x"), "none");
  assert.equal(tagStateOf([{ tags: ["y"] }], "x"), "none");
  assert.equal(tagStateOf([{ tags: ["x"] }, { tags: [] }], "x"), "some");
  assert.equal(tagStateOf([{ tags: ["x"] }, { tags: ["x", "y"] }], "x"), "all");
});

test("ajouter à une playlist garde l'ordre et ignore les doublons", () => {
  assert.deepEqual(mergedIds([3, 1], new Set([1, 5, 7])), [3, 1, 5, 7]);
});
