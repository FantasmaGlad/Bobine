import { test } from "node:test";
import assert from "node:assert/strict";

type Slot = 0 | 1;
type Track = { id: number };
type Repeat = "off" | "playlist" | "track";
type Announcement = { id: number; mode: "wait_end" | "duck" };
type Decks = { active: Slot; trackIds: [number | null, number | null]; crossfading: boolean };
type Duck = { level: number; fadeMs: number };

const other = (slot: Slot): Slot => (slot === 0 ? 1 : 0);

function setParamNow(param: FakeParam, value: number, now: number) {
  param.cancelScheduledValues(now);
  param.setValueAtTime(value, now);
}

function rampParam(param: FakeParam, to: number, durationMs: number, now: number) {
  param.cancelScheduledValues(now);
  param.setValueAtTime(param.value, now);
  param.linearRampToValueAtTime(to, now + Math.max(0.001, durationMs / 1000));
}

function crossfadeDurationMs(crossfadeSeconds: number) {
  return Math.max(200, crossfadeSeconds * 1000);
}

function crossfadeTarget(
  state: { order: Track[]; index: number | null; repeat: Repeat; crossfade_seconds: number },
  el: { duration: number; currentTime: number },
  flags: { crossfading: boolean; graphReady: boolean; announcing: boolean },
): Track | null {
  if (flags.crossfading || !flags.graphReady || flags.announcing) return null;
  if (state.repeat === "track") return null;
  const { duration, currentTime } = el;
  if (!isFinite(duration) || duration <= 0) return null;
  const crossfadeSeconds = Math.max(0, state.crossfade_seconds || 0);
  if (crossfadeSeconds <= 0 || duration - currentTime > crossfadeSeconds) return null;
  const { order, index } = state;
  if (index === null) return null;
  if (index + 1 < order.length) return order[index + 1];
  if (state.repeat === "playlist" && order.length > 0) return order[0];
  return null;
}

type TrackDecision = "unload" | "same" | "promote" | "load";

function decideTrack(trackId: number | null, decks: Decks): TrackDecision {
  if (trackId === null) return "unload";
  if (trackId === decks.trackIds[decks.active]) return "same";
  if (decks.crossfading && decks.trackIds[other(decks.active)] === trackId) return "promote";
  return "load";
}

function targetGain(decision: TrackDecision, ducking: boolean, volume: number, duck: Duck): number | null {
  if (decision === "same") return ducking ? null : volume / 100;
  if (decision === "promote" || decision === "load") return (ducking ? duck.level : volume) / 100;
  return null;
}

function transportAction(
  cause: string,
  announcement: Announcement | null,
  playing: boolean,
  paused: boolean,
): { seek: boolean; action: "play" | "pause" | "none" } {
  const seek = cause === "radio_seek" || cause === "radio_restart_track";
  if (announcement?.mode === "wait_end") return { seek, action: "none" };
  if (playing && paused) return { seek, action: "play" };
  if (!playing && !paused) return { seek, action: "pause" };
  return { seek, action: "none" };
}

type AnnouncementPlan =
  | { kind: "none" }
  | { kind: "start"; abortCrossfade: true; announcementGain: [number, number]; musicRamp: number | null; fadeMs: number }
  | { kind: "end"; announcementGain: [null, number]; musicRamp: number | null; unloadAfterMs: number };

function planAnnouncement(prev: Announcement | null, next: Announcement | null, volume: number, duck: Duck): AnnouncementPlan {
  if (next && next.id !== prev?.id) {
    return {
      kind: "start",
      abortCrossfade: true,
      announcementGain: [0, 1],
      musicRamp: next.mode === "duck" ? duck.level / 100 : null,
      fadeMs: duck.fadeMs,
    };
  }
  if (!next && prev) {
    return {
      kind: "end",
      announcementGain: [null, 0],
      musicRamp: prev.mode === "duck" ? volume / 100 : null,
      unloadAfterMs: duck.fadeMs,
    };
  }
  return { kind: "none" };
}

const STALL_TIMEOUT_MS = 15000;
const RECOVERY_GRACE_MS = 10000;

function stalled(playing: boolean, announcing: boolean, recovering: boolean, sinceProgressMs: number) {
  if (!playing || announcing || recovering) return false;
  return sinceProgressMs > STALL_TIMEOUT_MS;
}

function recoveryOutcome(
  progressedSinceAttempt: boolean,
  elapsedMs: number,
  stillActive: boolean,
  playing: boolean,
  announcing: boolean,
): "recovered" | "wait" | "skip" | "give_up" {
  if (progressedSinceAttempt) return "recovered";
  if (elapsedMs < RECOVERY_GRACE_MS) return "wait";
  return stillActive && playing && !announcing ? "skip" : "give_up";
}

class FakeParam {
  value: number;
  calls: [string, ...number[]][] = [];
  constructor(value = 0) { this.value = value; }
  cancelScheduledValues(t: number) { this.calls.push(["cancel", t]); }
  setValueAtTime(v: number, t: number) { this.calls.push(["set", v, t]); this.value = v; }
  linearRampToValueAtTime(v: number, t: number) { this.calls.push(["ramp", v, t]); }
}

const tracks = [{ id: 10 }, { id: 11 }, { id: 12 }];
const ready = { crossfading: false, graphReady: true, announcing: false };
const nearEnd = { duration: 200, currentTime: 197 };
const duck = { level: 15, fadeMs: 800 };

test("valeur immédiate : annulation puis valeur, dans cet ordre", () => {
  const p = new FakeParam(0.4);
  setParamNow(p, 0.7, 12);
  assert.deepEqual(p.calls, [["cancel", 12], ["set", 0.7, 12]]);
});

test("rampe : annulation, ancrage sur la valeur courante, rampe linéaire", () => {
  const p = new FakeParam(0.8);
  rampParam(p, 0, 5000, 3);
  assert.deepEqual(p.calls, [["cancel", 3], ["set", 0.8, 3], ["ramp", 0, 8]]);
});

test("rampe de durée nulle : borne basse d'une milliseconde", () => {
  const p = new FakeParam(1);
  rampParam(p, 0, 0, 2);
  assert.deepEqual(p.calls.at(-1), ["ramp", 0, 2.001]);
});

test("durée de fondu : 200 ms au minimum", () => {
  assert.equal(crossfadeDurationMs(5), 5000);
  assert.equal(crossfadeDurationMs(0.1), 200);
});

test("fondu : piste suivante dans la liste", () => {
  const state = { order: tracks, index: 0, repeat: "off" as Repeat, crossfade_seconds: 5 };
  assert.deepEqual(crossfadeTarget(state, nearEnd, ready), { id: 11 });
});

test("fondu : fin de liste sans répétition, aucune cible", () => {
  const state = { order: tracks, index: 2, repeat: "off" as Repeat, crossfade_seconds: 5 };
  assert.equal(crossfadeTarget(state, nearEnd, ready), null);
});

test("fondu : fin de liste en répétition de liste, retour au début", () => {
  const state = { order: tracks, index: 2, repeat: "playlist" as Repeat, crossfade_seconds: 5 };
  assert.deepEqual(crossfadeTarget(state, nearEnd, ready), { id: 10 });
});

test("fondu : répétition de piste, jamais de fondu", () => {
  const state = { order: tracks, index: 0, repeat: "track" as Repeat, crossfade_seconds: 5 };
  assert.equal(crossfadeTarget(state, nearEnd, ready), null);
});

test("fondu : durée nulle ou négative, aucun fondu", () => {
  for (const crossfade_seconds of [0, -3]) {
    const state = { order: tracks, index: 0, repeat: "off" as Repeat, crossfade_seconds };
    assert.equal(crossfadeTarget(state, { duration: 200, currentTime: 199.9 }, ready), null);
  }
});

test("fondu : trop tôt dans la piste, aucun fondu ; pile à la fenêtre, fondu", () => {
  const state = { order: tracks, index: 0, repeat: "off" as Repeat, crossfade_seconds: 5 };
  assert.equal(crossfadeTarget(state, { duration: 200, currentTime: 194.9 }, ready), null);
  assert.deepEqual(crossfadeTarget(state, { duration: 200, currentTime: 195 }, ready), { id: 11 });
});

test("fondu : durée inconnue, infinie ou nulle, aucun fondu", () => {
  const state = { order: tracks, index: 0, repeat: "off" as Repeat, crossfade_seconds: 5 };
  for (const duration of [NaN, Infinity, 0]) {
    assert.equal(crossfadeTarget(state, { duration, currentTime: 0 }, ready), null);
  }
});

test("fondu : bloqué pendant un fondu, sans graphe, pendant un rappel, sans index", () => {
  const state = { order: tracks, index: 0, repeat: "off" as Repeat, crossfade_seconds: 5 };
  assert.equal(crossfadeTarget(state, nearEnd, { ...ready, crossfading: true }), null);
  assert.equal(crossfadeTarget(state, nearEnd, { ...ready, graphReady: false }), null);
  assert.equal(crossfadeTarget(state, nearEnd, { ...ready, announcing: true }), null);
  assert.equal(crossfadeTarget({ ...state, index: null }, nearEnd, ready), null);
});

test("piste : absence de piste, les deux platines sont vidées", () => {
  assert.equal(decideTrack(null, { active: 0, trackIds: [10, 11], crossfading: true }), "unload");
});

test("piste : même piste sur la platine active", () => {
  assert.equal(decideTrack(10, { active: 0, trackIds: [10, null], crossfading: false }), "same");
  assert.equal(decideTrack(11, { active: 1, trackIds: [10, 11], crossfading: true }), "same");
});

test("piste : promotion de la platine en fondu", () => {
  assert.equal(decideTrack(11, { active: 0, trackIds: [10, 11], crossfading: true }), "promote");
});

test("piste : piste déjà sur l'autre platine sans fondu, chargement direct", () => {
  assert.equal(decideTrack(11, { active: 0, trackIds: [10, 11], crossfading: false }), "load");
});

test("piste : piste inconnue, chargement direct même pendant un fondu", () => {
  assert.equal(decideTrack(12, { active: 0, trackIds: [10, 11], crossfading: true }), "load");
  assert.equal(decideTrack(12, { active: 0, trackIds: [null, null], crossfading: false }), "load");
});

test("gain cible : volume, ou niveau d'atténuation pendant un rappel", () => {
  assert.equal(targetGain("same", false, 80, duck), 0.8);
  assert.equal(targetGain("same", true, 80, duck), null);
  assert.equal(targetGain("promote", false, 80, duck), 0.8);
  assert.equal(targetGain("promote", true, 80, duck), 0.15);
  assert.equal(targetGain("load", true, 80, duck), 0.15);
  assert.equal(targetGain("unload", false, 80, duck), null);
});

test("transport : saut sur seek et redémarrage de piste seulement", () => {
  assert.equal(transportAction("radio_seek", null, true, false).seek, true);
  assert.equal(transportAction("radio_restart_track", null, true, false).seek, true);
  assert.equal(transportAction("sync", null, true, false).seek, false);
});

test("transport : lecture, pause ou rien selon l'état", () => {
  assert.equal(transportAction("sync", null, true, true).action, "play");
  assert.equal(transportAction("sync", null, false, false).action, "pause");
  assert.equal(transportAction("sync", null, true, false).action, "none");
  assert.equal(transportAction("sync", null, false, true).action, "none");
});

test("transport : rappel en attente de fin, la musique n'est ni lancée ni arrêtée", () => {
  const ann = { id: 1, mode: "wait_end" as const };
  assert.equal(transportAction("sync", ann, true, true).action, "none");
  assert.equal(transportAction("sync", ann, false, false).action, "none");
});

test("rappel qui commence en atténuation : fondu entrant et musique au niveau réduit", () => {
  assert.deepEqual(planAnnouncement(null, { id: 1, mode: "duck" }, 80, duck), {
    kind: "start", abortCrossfade: true, announcementGain: [0, 1], musicRamp: 0.15, fadeMs: 800,
  });
});

test("rappel qui commence en attente de fin : musique laissée telle quelle", () => {
  const plan = planAnnouncement(null, { id: 1, mode: "wait_end" }, 80, duck);
  assert.equal(plan.kind, "start");
  assert.equal(plan.kind === "start" && plan.musicRamp, null);
});

test("rappel remplacé par un autre : nouveau départ, pas de fin", () => {
  const plan = planAnnouncement({ id: 1, mode: "duck" }, { id: 2, mode: "wait_end" }, 80, duck);
  assert.equal(plan.kind, "start");
});

test("même rappel : rien", () => {
  assert.deepEqual(planAnnouncement({ id: 1, mode: "duck" }, { id: 1, mode: "duck" }, 80, duck), { kind: "none" });
  assert.deepEqual(planAnnouncement(null, null, 80, duck), { kind: "none" });
});

test("rappel qui finit : fondu sortant, retour au volume si atténué, déchargement après le fondu", () => {
  assert.deepEqual(planAnnouncement({ id: 1, mode: "duck" }, null, 80, duck), {
    kind: "end", announcementGain: [null, 0], musicRamp: 0.8, unloadAfterMs: 800,
  });
  const waitEnd = planAnnouncement({ id: 1, mode: "wait_end" }, null, 80, duck);
  assert.equal(waitEnd.kind === "end" && waitEnd.musicRamp, null);
});

test("rappel pendant un fondu : le fondu est abandonné, puis la piste se décide en atténuation", () => {
  const plan = planAnnouncement(null, { id: 3, mode: "duck" }, 60, duck);
  assert.equal(plan.kind === "start" && plan.abortCrossfade, true);
  const decks: Decks = { active: 0, trackIds: [10, null], crossfading: false };
  assert.equal(decideTrack(10, decks), "same");
  assert.equal(targetGain("same", true, 60, duck), null);
});

test("chien de garde : blocage au-delà de 15 s de lecture sans progrès", () => {
  assert.equal(stalled(true, false, false, 15001), true);
  assert.equal(stalled(true, false, false, 15000), false);
  assert.equal(stalled(false, false, false, 60000), false);
  assert.equal(stalled(true, true, false, 60000), false);
  assert.equal(stalled(true, false, true, 60000), false);
});

test("reprise : progrès, attente, piste suivante après 10 s, ou abandon", () => {
  assert.equal(recoveryOutcome(true, 20000, true, true, false), "recovered");
  assert.equal(recoveryOutcome(false, 9999, true, true, false), "wait");
  assert.equal(recoveryOutcome(false, 10000, true, true, false), "skip");
  assert.equal(recoveryOutcome(false, 10000, false, true, false), "give_up");
  assert.equal(recoveryOutcome(false, 10000, true, false, false), "give_up");
  assert.equal(recoveryOutcome(false, 10000, true, true, true), "give_up");
});
