import { test } from "node:test";
import assert from "node:assert/strict";
import { RETRY_MS, SignageEngine, type Stage } from "../src/components/signage/engine/engine.ts";
import type { Slide } from "../src/components/signage/engine/slide.ts";
import { planSlot, type SignageEntry } from "../src/lib/signageLoop.ts";

const entry = (id: number, is_image: boolean, play_seconds: number | null): SignageEntry => ({
  background_id: id, seconds: play_seconds, title: `visuel ${id}`, is_image, play_seconds, duration_seconds: null,
});

class FakeSlide implements Slide {
  readonly element = {} as HTMLElement;
  started = 0;
  disposed = 0;
  ended: (() => void) | null = null;
  readonly id: number;
  readonly loop: boolean;
  constructor(id: number, loop: boolean) {
    this.id = id;
    this.loop = loop;
  }
  start() { this.started += 1; }
  onEnded(listener: () => void) { this.ended = listener; }
  dispose() { this.disposed += 1; }
}

function rig(broken: Set<number> = new Set()) {
  const shown: FakeSlide[] = [];
  const prepared: FakeSlide[] = [];
  const stage: Stage = { show: (slide) => shown.push(slide as FakeSlide), clear: () => undefined };
  const engine = new SignageEngine(stage, async (e, loop) => {
    if (broken.has(e.background_id)) return null;
    const slide = new FakeSlide(e.background_id, loop);
    prepared.push(slide);
    return slide;
  });
  return { engine, shown, prepared };
}

const settle = () => new Promise<void>((resolve) => setImmediate(resolve));

test("une image seule reste affichée et une vidéo seule boucle", () => {
  assert.deepEqual(planSlot(entry(1, true, 10), true), { holdMs: null, loop: true, advances: false });
  assert.deepEqual(planSlot(entry(1, false, null), false), { holdMs: null, loop: false, advances: true });
  assert.deepEqual(planSlot(entry(1, false, 20), false), { holdMs: 20000, loop: true, advances: true });
});

test("l'élément suivant est préparé pendant l'affichage du courant, puis réutilisé", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { engine, shown, prepared } = rig();
  engine.load([entry(1, true, 3), entry(2, true, 4)]);
  t.mock.timers.tick(0);
  await settle();
  assert.deepEqual(shown.map((s) => s.id), [1]);
  assert.deepEqual(prepared.map((s) => s.id), [1, 2]);
  t.mock.timers.tick(3000);
  await settle();
  assert.deepEqual(shown.map((s) => s.id), [1, 2]);
  assert.equal(prepared.filter((s) => s.id === 2).length, 1);
  engine.stop();
});

test("une vidéo entière passe à la suite à sa fin", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { engine, shown } = rig();
  engine.load([entry(1, false, null), entry(2, true, 5)]);
  t.mock.timers.tick(0);
  await settle();
  assert.equal(shown[0].loop, false);
  shown[0].ended?.();
  await settle();
  assert.deepEqual(shown.map((s) => s.id), [1, 2]);
  engine.stop();
});

test("un visuel illisible est sauté et une boucle entièrement illisible réessaie sans tourner à vide", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { engine, shown } = rig(new Set([2]));
  engine.load([entry(1, true, 3), entry(2, true, 3), entry(3, true, 3)]);
  t.mock.timers.tick(0);
  await settle();
  t.mock.timers.tick(3000);
  await settle();
  t.mock.timers.tick(0);
  await settle();
  assert.deepEqual(shown.map((s) => s.id), [1, 3]);
  engine.stop();

  const dead = rig(new Set([1, 2]));
  dead.engine.load([entry(1, true, 3), entry(2, true, 3)]);
  t.mock.timers.tick(0);
  await settle();
  t.mock.timers.tick(0);
  await settle();
  assert.equal(dead.shown.length, 0);
  t.mock.timers.tick(RETRY_MS - 1);
  await settle();
  assert.equal(dead.shown.length, 0);
  dead.engine.stop();
});

test("recharger la boucle libère l'élément préparé de l'ancienne", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { engine, prepared, shown } = rig();
  engine.load([entry(1, true, 3), entry(2, true, 3)]);
  t.mock.timers.tick(0);
  await settle();
  engine.load([entry(7, true, 3), entry(8, true, 3)]);
  t.mock.timers.tick(0);
  await settle();
  assert.equal(prepared.find((s) => s.id === 2)?.disposed, 1);
  assert.deepEqual(shown.map((s) => s.id), [1, 7]);
  engine.stop();
});
