import { test } from "node:test";
import assert from "node:assert/strict";
import { ButtonRepeat, REPEAT_DELAY_MS, REPEAT_RATE_MS } from "../src/lib/input/repeat.ts";

test("un bouton tire à l'appui puis plus jamais tant qu'il reste enfoncé", () => {
  const repeat = new ButtonRepeat();
  assert.equal(repeat.fires("a", true, false, 0), true);
  assert.equal(repeat.fires("a", true, false, 5000), false);
  assert.equal(repeat.fires("a", false, false, 5100), false);
  assert.equal(repeat.fires("a", true, false, 5200), true);
});

test("une direction tenue se répète après le délai, au rythme fixé", () => {
  const repeat = new ButtonRepeat();
  const fired: number[] = [];
  for (let now = 0; now <= REPEAT_DELAY_MS + 3 * REPEAT_RATE_MS; now += 10) {
    if (repeat.fires("up", true, true, now)) fired.push(now);
  }
  const repeats = [1, 2, 3].map((n) => REPEAT_DELAY_MS + n * REPEAT_RATE_MS);
  assert.deepEqual(fired, [0, ...repeats]);
});

test("chaque bouton a son propre état", () => {
  const repeat = new ButtonRepeat();
  assert.equal(repeat.fires("gp_0_12", true, true, 0), true);
  assert.equal(repeat.fires("gp_1_12", true, true, 10), true);
});
