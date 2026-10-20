import { test } from "node:test";
import assert from "node:assert/strict";
import { appendDigit, deleteDigit, emptyPin, initialSetFlow, isComplete, keyToAction, submitSetCode } from "../src/lib/pinEntry.ts";

test("saisie : chiffres seulement, bornée à la longueur, retour arrière", () => {
  let pin = emptyPin(6);
  for (const k of "12a3-45") pin = appendDigit(pin, k);
  assert.equal(pin.digits, "12345");
  pin = appendDigit(pin, "6");
  assert.equal(isComplete(pin), true);
  assert.equal(appendDigit(pin, "7").digits, "123456"); // plein : ignoré
  assert.equal(deleteDigit(pin).digits, "12345");
  assert.equal(deleteDigit(emptyPin()).digits, "");
});

test("touches physiques", () => {
  assert.deepEqual(keyToAction("7"), { type: "digit", digit: "7" });
  assert.deepEqual(keyToAction("Backspace"), { type: "delete" });
  assert.equal(keyToAction("a"), null);
  assert.equal(keyToAction("Enter"), null);
});

test("définition en deux temps : confirmation identique", () => {
  const first = submitSetCode(initialSetFlow, "123456");
  assert.equal(first.kind, "next");
  assert.equal(first.flow.phase, "confirm");
  const done = submitSetCode(first.flow, "123456");
  assert.deepEqual([done.kind, done.kind === "done" ? done.pin : null], ["done", "123456"]);
  assert.equal(done.flow.first, ""); // le premier code n'est pas conservé
});

test("définition : écart = retour au premier temps, code oublié", () => {
  const first = submitSetCode(initialSetFlow, "123456");
  const bad = submitSetCode(first.flow, "654321");
  assert.equal(bad.kind, "mismatch");
  assert.deepEqual(bad.flow, { phase: "new", first: "", mismatch: true });
});
