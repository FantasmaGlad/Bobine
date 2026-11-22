import { test } from "node:test";
import assert from "node:assert/strict";
import { kioskFeedback } from "../src/lib/kioskFeedback.ts";

test("un saut affiche la barre de lecture seule, sans second bandeau", () => {
  const feedback = kioskFeedback("seek", { position_seconds: 1550, current_video: { duration_seconds: 3230 } });
  assert.deepEqual(feedback, { seekHud: { position: 1550, duration: 3230 } });
});

test("un changement de vitesse garde son bandeau", () => {
  assert.deepEqual(kioskFeedback("speed", { speed: 1.25 }), { osd: { icon: "speed", label: "1.25x" } });
});

test("les autres évènements n'affichent rien", () => {
  assert.equal(kioskFeedback("play", {}), null);
});
