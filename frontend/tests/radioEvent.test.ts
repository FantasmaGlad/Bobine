import assert from "node:assert/strict";
import test from "node:test";

import { mergeRadioState, type RadioStatePatch } from "../src/lib/radioEvent.ts";
import type { RadioState } from "../src/lib/useRadioSocket.ts";

const track = (id: number) => ({ id, title: `T${id}`, artist: null, album: null, duration_seconds: 60, cover_url: null });
const base = { state: "playing", index: 0, position_seconds: 1, order: [track(1), track(2)] } as unknown as RadioState;

test("un évènement sans file garde la file connue, à la même référence", () => {
  const tick: RadioStatePatch = { ...base, position_seconds: 2 };
  delete tick.order;
  const next = mergeRadioState(base, tick);
  assert.equal(next.order, base.order);
  assert.equal(next.position_seconds, 2);
});

test("un évènement avec file la remplace", () => {
  const order = [track(2), track(1)];
  const next = mergeRadioState(base, { ...base, order });
  assert.equal(next.order, order);
});
