import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ClockOffsetEstimator,
  DRIFT_HARD_SEEK_S,
  EXPLICIT_SEEK_S,
  MAX_RATE_ADJUST,
  anchorPosition,
  msUntilStart,
  planDrift,
} from "../src/lib/playbackClock.ts";

const anchor = { pos: 10, at_ms: 1_000_000, rate: 1, running: true };

test("position cible : avance depuis l'ancre, figée avant l'instant de départ", () => {
  assert.equal(anchorPosition(anchor, 1_000_000), 10);
  assert.equal(anchorPosition(anchor, 1_004_000), 14);
  assert.equal(anchorPosition(anchor, 999_000), 10); // départ dans le futur
  assert.equal(anchorPosition({ ...anchor, rate: 2 }, 1_003_000), 16);
  assert.equal(anchorPosition({ ...anchor, running: false }, 1_900_000), 10);
});

test("délai avant démarrage synchronisé", () => {
  assert.equal(msUntilStart(anchor, 999_250), 750);
  assert.equal(msUntilStart(anchor, 1_000_500), 0);
  assert.equal(msUntilStart({ ...anchor, running: false }, 0), 0);
});

test("dérive négligeable : aucune action, vitesse nominale", () => {
  assert.deepEqual(planDrift(0.02, 1, false), { action: "none", playbackRate: 1 });
  assert.deepEqual(planDrift(-0.07, 1, false), { action: "none", playbackRate: 1 });
});

test("en retard -> accélère, en avance -> ralentit, jamais au-delà de ±5 %", () => {
  const late = planDrift(-0.2, 1, false);
  assert.equal(late.action, "rate");
  assert.ok(late.playbackRate > 1 && late.playbackRate <= 1 + MAX_RATE_ADJUST + 1e-9);
  const ahead = planDrift(0.5, 1, false);
  assert.equal(ahead.action, "rate");
  assert.ok(ahead.playbackRate < 1 && ahead.playbackRate >= 1 - MAX_RATE_ADJUST - 1e-9);
  assert.ok(Math.abs(planDrift(1.9, 1, false).playbackRate - 0.95) < 1e-9);
});

test("la vitesse nominale choisie par l'utilisateur est respectée", () => {
  assert.equal(planDrift(0, 1.5, false).playbackRate, 1.5);
  const p = planDrift(-0.2, 1.5, false);
  assert.ok(p.playbackRate > 1.5 && p.playbackRate <= 1.5 * 1.05 + 1e-9);
});

test("hystérésis : une correction en cours ne s'arrête qu'en dessous du seuil de sortie", () => {
  assert.equal(planDrift(0.05, 1, false).action, "none");
  assert.equal(planDrift(0.05, 1, true).action, "rate");
  assert.equal(planDrift(0.02, 1, true).action, "none");
});

test("dérive forte -> un seul seek, vitesse nominale", () => {
  assert.deepEqual(planDrift(DRIFT_HARD_SEEK_S, 1, false), { action: "seek", playbackRate: 1 });
  assert.deepEqual(planDrift(-5, 1, true), { action: "seek", playbackRate: 1 });
});

test("convergence : la correction de vitesse ramène la dérive sous le seuil sans seek", () => {
  let drift = 0.6; // 600 ms d'avance
  let correcting = false;
  let seeks = 0;
  for (let second = 0; second < 40; second++) {
    const plan = planDrift(drift, 1, correcting);
    if (plan.action === "seek") seeks++;
    correcting = plan.action === "rate";
    drift += plan.playbackRate - 1; // 1 s écoulée à cette vitesse
  }
  assert.equal(seeks, 0);
  assert.ok(Math.abs(drift) < 0.08, `dérive finale ${drift}`);
});

test("estimation d'horloge : retient les échantillons au plus petit RTT", () => {
  const e = new ClockOffsetEstimator();
  assert.equal(e.offsetMs(), 0);
  // Vrai décalage = +500 ms (serveur en avance). Échantillons bruités par la latence.
  const truth = 500;
  const sample = (send: number, up: number, down: number) =>
    e.add(send, send + up + truth, send + up + down);
  sample(0, 5, 5);       // RTT 10, symétrique : offset exact
  sample(1000, 120, 10); // RTT 130, asymétrique : biaisé
  sample(2000, 6, 4);    // RTT 10
  sample(3000, 300, 20); // RTT 320
  assert.ok(Math.abs(e.offsetMs() - truth) < 5, `offset ${e.offsetMs()}`);
  assert.equal(e.bestRttMs(), 10);
});

test("estimation d'horloge : échantillons invalides ignorés, fenêtre bornée", () => {
  const e = new ClockOffsetEstimator(4);
  e.add(100, 0, 50); // réception avant envoi
  assert.equal(e.count, 0);
  for (let i = 0; i < 10; i++) e.add(i * 100, i * 100 + 5, i * 100 + 10);
  assert.equal(e.count, 4);
});

test("ordre explicite : seek immédiat dès 0,3 s d'écart, sans attendre la convergence", () => {
  // Dérive de 0,5 s : en régime normal on corrige par la vitesse...
  assert.equal(planDrift(0.5, 1, false).action, "rate");
  // ...mais juste après un ordre (seek +10 s à la télécommande) on replace le média.
  assert.deepEqual(planDrift(0.5, 1, false, true), { action: "seek", playbackRate: 1 });
  assert.equal(planDrift(-10, 1, false, true).action, "seek");
  // Sous le seuil explicite, rien de brutal.
  assert.notEqual(planDrift(EXPLICIT_SEEK_S - 0.05, 1, false, true).action, "seek");
});
