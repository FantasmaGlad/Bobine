import { test } from "node:test";
import assert from "node:assert/strict";
import {
  clampMix, dbToGain, defaultMix, effectiveGains, formatDb, GAIN_MAX_DB, GAIN_MIN_DB, hasSolo, meterLevel, smoothLevel, stripAudible, toMixerParams,
} from "../src/lib/radioMix.ts";
import { LIMITER_OFF, LIMITER_ON } from "../src/lib/radioSound.ts";

test("réglages neutres : tout à 0 dB, rien de coupé, aucun solo", () => {
  const mix = defaultMix();
  assert.deepEqual(effectiveGains(mix), { music: 1, announcements: 1, master: 1 });
  assert.equal(hasSolo(mix), false);
  mix.music.gain_db = 5; // copie indépendante
  assert.equal(defaultMix().music.gain_db, 0);
});

test("gains hors plage bornés, arrondis comme le serveur (Math.round), types invalides ignorés", () => {
  const mix = clampMix({ master: { gain_db: 99 }, music: { gain_db: -99 }, announcements: { gain_db: 2.5 } });
  assert.equal(mix.master.gain_db, GAIN_MAX_DB);
  assert.equal(mix.music.gain_db, GAIN_MIN_DB);
  assert.equal(mix.announcements.gain_db, 3);
  assert.equal(clampMix({ music: { gain_db: -2.5 } }).music.gain_db, -2);
  const base = clampMix({ music: { gain_db: -6, muted: true, solo: true } });
  const kept = clampMix({ music: { gain_db: "fort" as unknown as number, muted: "oui" as unknown as boolean } }, base);
  assert.deepEqual(kept.music, { gain_db: -6, muted: true, solo: true });
  assert.deepEqual(clampMix(null), defaultMix());
  assert.deepEqual(clampMix(undefined), defaultMix());
  assert.equal(clampMix({ music: { gain_db: NaN } }).music.gain_db, 0);
});

test("égaliseur des rappels borné comme celui de la musique", () => {
  const mix = clampMix({ announcements: { sound: { bands: [99, -99, 0, 0, 0], bass_boost: 99 } } });
  assert.deepEqual(mix.announcements.sound.bands.slice(0, 2), [12, -12]);
  assert.equal(mix.announcements.sound.bass_boost, 12);
});

test("sourdine et fader : gain linéaire en dB", () => {
  const mix = clampMix({ music: { gain_db: -6 }, announcements: { muted: true }, master: { gain_db: -20 } });
  const g = effectiveGains(mix);
  assert.ok(Math.abs(g.music - dbToGain(-6)) < 1e-9);
  assert.equal(g.announcements, 0);
  assert.ok(Math.abs(g.master - 0.1) < 1e-9);
  assert.equal(effectiveGains(clampMix({ master: { muted: true } })).master, 0);
});

test("solo : les autres tranches sont coupées, la sortie ne l'est pas ; sourdine prioritaire sur solo", () => {
  const solo = clampMix({ announcements: { solo: true } });
  assert.deepEqual(effectiveGains(solo), { music: 0, announcements: 1, master: 1 });
  assert.equal(hasSolo(solo), true);
  const both = clampMix({ music: { solo: true }, announcements: { solo: true } });
  assert.deepEqual(effectiveGains(both), { music: 1, announcements: 1, master: 1 });
  const soloMuted = clampMix({ music: { solo: true, muted: true } });
  assert.deepEqual(effectiveGains(soloMuted), { music: 0, announcements: 0, master: 1 });
});

test("limiteur de sortie actif seulement si un fader relève le son", () => {
  assert.deepEqual(toMixerParams(defaultMix()).limiter, LIMITER_OFF);
  assert.deepEqual(toMixerParams(clampMix({ music: { gain_db: -10 } })).limiter, LIMITER_OFF);
  assert.deepEqual(toMixerParams(clampMix({ announcements: { gain_db: 3 } })).limiter, LIMITER_ON);
  assert.deepEqual(toMixerParams(clampMix({ master: { gain_db: 1 } })).limiter, LIMITER_ON);
});

test("audibilité d'une tranche pour l'affichage", () => {
  const mix = clampMix({ music: { solo: true } });
  assert.equal(stripAudible(mix, "music"), true);
  assert.equal(stripAudible(mix, "announcements"), false);
  assert.equal(stripAudible(clampMix({ master: { muted: true } }), "music"), false);
});

test("vumètre : échelle dBFS −60…0 sur 0…100, bornée", () => {
  assert.equal(meterLevel(0), 0);
  assert.equal(meterLevel(-1), 0);
  assert.equal(meterLevel(NaN), 0);
  assert.equal(meterLevel(1), 100);
  assert.equal(meterLevel(5), 100);
  assert.equal(meterLevel(0.001), 0); // −60 dBFS
  assert.equal(meterLevel(0.5), 90); // −6 dBFS
  assert.ok(meterLevel(0.01) > 0 && meterLevel(0.01) < meterLevel(0.1));
});

test("retombée douce de l'aiguille", () => {
  assert.equal(smoothLevel(10, 50), 50);
  assert.equal(smoothLevel(80, 10), 68);
  assert.equal(smoothLevel(80, 75), 75);
  assert.equal(smoothLevel(80, 10, 30), 50);
});

test("format des dB", () => {
  assert.equal(formatDb(3), "+3 dB");
  assert.equal(formatDb(0), "0 dB");
  assert.equal(formatDb(-12), "-12 dB");
});
