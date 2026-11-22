import { test } from "node:test";
import assert from "node:assert/strict";
import { SCRUB_COMMIT_DELAY_MS, Scrubber, scrubStep } from "../src/lib/scrub.ts";

function harness() {
  let now = 0;
  const timers = new Map<number, { at: number; run: () => void }>();
  let nextId = 1;
  const previews: number[] = [];
  const commits: number[] = [];
  const scrubber = new Scrubber(
    {
      now: () => now,
      setTimer: (run, delay) => { const id = nextId++; timers.set(id, { at: now + delay, run }); return id; },
      clearTimer: (id) => { timers.delete(id as number); },
    },
  );
  const target = { onPreview: (s: number) => previews.push(s), onCommit: (s: number) => commits.push(s) };
  const advance = (ms: number) => {
    now += ms;
    for (const [id, timer] of [...timers]) if (timer.at <= now) { timers.delete(id); timer.run(); }
  };
  const press = (direction: 1 | -1, current: number, duration: number) => scrubber.press(direction, current, duration, target);
  return { press, advance, previews, commits };
}

test("le pas grandit avec la durée de l'appui", () => {
  assert.deepEqual([0, 900, 2500, 5000].map(scrubStep), [10, 30, 60, 120]);
});

test("un appui bref fait un seul saut de 10 s", () => {
  const h = harness();
  h.press(1, 100, 3000);
  assert.deepEqual(h.previews, [110]);
  assert.deepEqual(h.commits, []);
  h.advance(SCRUB_COMMIT_DELAY_MS);
  assert.deepEqual(h.commits, [110]);
});

test("un appui long répété à 30 Hz n'envoie qu'un saut et accélère", () => {
  const h = harness();
  for (let elapsed = 0; elapsed <= 3000; elapsed += 33) {
    h.press(1, 100, 3000);
    h.advance(33);
  }
  assert.equal(h.commits.length, 0);
  assert.ok(h.previews.length < 3000 / 33 / 2, "les répétitions trop rapprochées sont regroupées");
  const steps = h.previews.map((value, i) => value - (i === 0 ? 100 : h.previews[i - 1]));
  assert.equal(steps[0], 10);
  assert.ok(steps.at(-1)! >= 60, "le pas a accéléré");
  h.advance(SCRUB_COMMIT_DELAY_MS);
  assert.deepEqual(h.commits, [h.previews.at(-1)]);
});

test("la cible reste dans la vidéo et un changement de sens repart de la cible", () => {
  const h = harness();
  h.press(-1, 5, 3000);
  assert.deepEqual(h.previews, [0]);
  h.advance(200);
  h.press(1, 999, 3000);
  assert.equal(h.previews.at(-1), 10);
  h.advance(SCRUB_COMMIT_DELAY_MS);
  assert.deepEqual(h.commits, [10]);
  h.press(1, 2995, 3000);
  assert.equal(h.previews.at(-1), 3000);
});
