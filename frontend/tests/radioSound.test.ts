import { test } from "node:test";
import assert from "node:assert/strict";
import {
  BAND_COUNT,
  BAND_FREQUENCIES,
  BAND_GAIN_MAX_DB,
  BAND_GAIN_MIN_DB,
  BASS_BOOST_MAX_DB,
  PRESETS,
  applyPreset,
  clampSound,
  computePreamp,
  defaultSound,
  knownPresetId,
  matchingPreset,
  peakBoostDb,
  toGraphParams,
} from "../src/lib/radioSound.ts";

test("réglages neutres : une copie indépendante à chaque appel", () => {
  const a = defaultSound();
  a.bands[0] = 9;
  assert.equal(defaultSound().bands[0], 0);
  assert.equal(defaultSound().enabled, true);
});

test("les gains hors plage sont bornés, jamais d'exception", () => {
  const s = clampSound({ bands: [99, -99, 3.6, 0, 12], bass_boost: 50 });
  assert.deepEqual(s.bands, [12, -12, 4, 0, 12]);
  assert.equal(s.bass_boost, BASS_BOOST_MAX_DB);
  assert.equal(clampSound({ bass_boost: -5 }).bass_boost, 0);
});

test("les valeurs invalides gardent la valeur de base", () => {
  const base = { enabled: false, bands: [1, 2, 3, 4, 5], bass_boost: 6, loudness: true, limiter: false, preset: "voice" };
  const s = clampSound(
    { bands: ["x", null, NaN, undefined, 7] as unknown as number[], bass_boost: "fort" as unknown as number, loudness: "oui" as unknown as boolean },
    base,
  );
  assert.deepEqual(s.bands, [1, 2, 3, 4, 7]);
  assert.equal(s.bass_boost, 6);
  assert.equal(s.loudness, true);
  assert.equal(s.enabled, false);
  assert.equal(s.preset, "voice");
  assert.deepEqual(clampSound(null), defaultSound());
});

test("tous les préréglages sont dans les bornes et ont cinq bandes", () => {
  assert.equal(BAND_FREQUENCIES.length, BAND_COUNT);
  for (const p of PRESETS) {
    assert.equal(p.bands.length, BAND_COUNT, p.id);
    for (const g of p.bands) assert.ok(g >= BAND_GAIN_MIN_DB && g <= BAND_GAIN_MAX_DB, p.id);
    assert.ok(p.bass_boost >= 0 && p.bass_boost <= BASS_BOOST_MAX_DB, p.id);
  }
  assert.equal(new Set(PRESETS.map((p) => p.id)).size, PRESETS.length);
  assert.deepEqual(PRESETS.map((p) => p.id), ["bass", "voice", "soft"]);
});

test("appliquer un préréglage change les gains et garde les interrupteurs", () => {
  const current = { ...defaultSound(), limiter: false, enabled: true };
  const out = applyPreset("bass", current);
  assert.equal(out.preset, "bass");
  assert.equal(out.limiter, false);
  assert.ok(out.bands[0] > 0 && out.bass_boost > 0);
  // Préréglage inconnu : inchangé.
  assert.equal(applyPreset("inconnu", current), current);
});

test("un réglage identique à un préréglage est reconnu, sinon manuel", () => {
  assert.equal(matchingPreset(applyPreset("voice", defaultSound())), "voice");
  assert.equal(matchingPreset(applyPreset("soft", defaultSound())), "soft");
  // À plat : aucun préréglage (le son neutre n'en est pas un).
  assert.equal(matchingPreset(defaultSound()), null);
  assert.equal(matchingPreset({ ...defaultSound(), bands: [1, 0, 0, 0, 0] }), null);
});

test("le préampli ne donne jamais de gain positif et compense le pire relèvement", () => {
  assert.equal(computePreamp(defaultSound()), 1);
  const boosted = { ...defaultSound(), bands: [6, 0, 0, 0, 0], bass_boost: 6 };
  assert.equal(peakBoostDb(boosted), 12);
  assert.ok(Math.abs(computePreamp(boosted) - Math.pow(10, -12 / 20)) < 1e-9);
  const cutOnly = { ...defaultSound(), bands: [-6, -6, -6, -6, -6] };
  assert.equal(computePreamp(cutOnly), 1);
  const extreme = { ...defaultSound(), bands: [12, 12, 12, 12, 12], bass_boost: 12, loudness: true };
  assert.ok(computePreamp(extreme) >= Math.pow(10, -18 / 20) - 1e-9, "atténuation plafonnée");
  assert.ok(computePreamp(extreme) <= 1);
});

test("son neutre : tous les filtres à 0 dB, préampli à 1, limiteur transparent", () => {
  const p = toGraphParams({ ...applyPreset("bass", defaultSound()), enabled: false });
  assert.equal(p.preampGain, 1);
  for (const b of p.bands) assert.equal(b.gain, 0);
  assert.equal(p.bass.gain, 0);
  assert.equal(p.loudnessLow.gain, 0);
  assert.equal(p.limiter.ratio, 1);
});

test("paramètres du graphe : fréquences, formes de filtres et gains reportés", () => {
  const s = clampSound({ bands: [3, -2, 1, 0, 4], bass_boost: 5, loudness: true, limiter: true });
  const p = toGraphParams(s);
  assert.deepEqual(p.bands.map((b) => b.frequency), [...BAND_FREQUENCIES]);
  assert.deepEqual(p.bands.map((b) => b.type), ["lowshelf", "peaking", "peaking", "peaking", "highshelf"]);
  assert.deepEqual(p.bands.map((b) => b.gain), [3, -2, 1, 0, 4]);
  assert.equal(p.bass.gain, 5);
  assert.equal(p.loudnessLow.gain, 4);
  assert.equal(p.loudnessHigh.gain, 3);
  assert.ok(p.limiter.ratio > 1);
  // Déterministe.
  assert.deepEqual(toGraphParams(s), p);
});

test("à plat, le limiteur reste transparent (la musique n'est pas modifiée)", () => {
  assert.equal(toGraphParams(defaultSound()).limiter.ratio, 1);
  // Dès qu'un réglage relève le son, la protection s'enclenche.
  assert.ok(toGraphParams({ ...defaultSound(), bands: [5, 0, 0, 0, 0] }).limiter.ratio > 1);
  // Une simple atténuation n'en a pas besoin.
  assert.equal(toGraphParams({ ...defaultSound(), bands: [-5, -5, -5, -5, -5] }).limiter.ratio, 1);
});

test("loudness et limiteur désactivés : transparents", () => {
  const p = toGraphParams(clampSound({ loudness: false, limiter: false }));
  assert.equal(p.loudnessLow.gain, 0);
  assert.equal(p.loudnessHigh.gain, 0);
  assert.equal(p.limiter.ratio, 1);
});

test("un ancien identifiant de préréglage disparu n'est plus reconnu", () => {
  for (const old of ["flat", "bright", "cardio", "n'importe quoi", "", null, undefined]) {
    assert.equal(knownPresetId(old as string | null | undefined), null, String(old));
  }
  for (const id of ["bass", "voice", "soft"]) assert.equal(knownPresetId(id), id);
  assert.equal(defaultSound().preset, null);
});
