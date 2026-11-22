import { test } from "node:test";
import assert from "node:assert/strict";
import { inputRows, pressedButton, sourceFromKey, splitSource } from "../src/lib/inputSource.ts";

test("une touche nommée donne key:, une touche inconnue son code Android", () => {
  assert.equal(sourceFromKey("ArrowLeft", 37), "key:ArrowLeft");
  assert.equal(sourceFromKey("Unidentified", 166), "code:166");
  assert.equal(sourceFromKey("", 23), "code:23");
});

test("seul un bouton nouvellement enfoncé est capturé", () => {
  assert.equal(pressedButton([false, true], [false, true]), null);
  assert.equal(pressedButton([false, true], [true, true]), 0);
  assert.equal(pressedButton([], Array(25).fill(false).map((_, i) => i === 22)), null);
});

test("les lignes suivent l'ordre clavier, codes, manette et marquent les choix", () => {
  const rows = inputRows({ "pad:0": ["enter"], "key:ArrowLeft": ["left"], "code:166": ["chapter_next"] }, { "key:F1": ["next"], "key:ArrowLeft": [] });
  assert.deepEqual(rows.map((row) => row.source), ["key:ArrowLeft", "key:F1", "code:166", "pad:0"]);
  assert.equal(rows[0].disabled, true);
  assert.equal(rows[1].custom, true);
  assert.deepEqual(splitSource("key: "), { kind: "key", value: " " });
});
