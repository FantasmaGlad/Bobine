import { test } from "node:test";
import assert from "node:assert/strict";
import { isLockedByEnvironment, parseMediaNativeStatus, stateKey } from "../src/lib/mediaNative.ts";
import { dictionaries as translations } from "../src/lib/i18n.ts";

const base = {
  enabled: true, setting: true, source: "setting", forced_by_env: null, available: true,
  state: "active", binary_version: "0.1.0", formats: ["mp3", "m4a"], reason: null,
};

test("une réponse valide est reconnue et normalisée", () => {
  const status = parseMediaNativeStatus(base);
  assert.ok(status);
  assert.equal(status.state, "active");
  assert.deepEqual(status.formats, ["mp3", "m4a"]);
  assert.equal(stateKey(status), "state_active");
});

test("une réponse invalide ou inconnue donne un état indisponible, jamais « actif »", () => {
  for (const bad of [null, undefined, 3, "x", {}, { ...base, state: "on" }, { ...base, enabled: "yes" }]) {
    assert.equal(parseMediaNativeStatus(bad), null);
  }
  assert.equal(stateKey(null), "stateUnknown");
});

test("les quatre états ont chacun leur texte", () => {
  for (const state of ["disabled", "active", "fallback", "absent"]) {
    const status = parseMediaNativeStatus({ ...base, state, enabled: state !== "disabled" });
    assert.equal(stateKey(status), `state_${state}`);
  }
});

test("la variable d'environnement verrouille la case dans les deux sens", () => {
  assert.equal(isLockedByEnvironment(parseMediaNativeStatus({ ...base, forced_by_env: true })), true);
  assert.equal(isLockedByEnvironment(parseMediaNativeStatus({ ...base, forced_by_env: false })), true);
  assert.equal(isLockedByEnvironment(parseMediaNativeStatus(base)), false);
  assert.equal(isLockedByEnvironment(null), false);
});

test("textes français et anglais complets, avec les mêmes clés", () => {
  const fr = (translations as Record<string, Record<string, Record<string, string>>>).fr.mediaNative;
  const en = (translations as Record<string, Record<string, Record<string, string>>>).en.mediaNative;
  assert.ok(fr && en);
  assert.deepEqual(Object.keys(fr).sort(), Object.keys(en).sort());
  for (const key of Object.keys(fr)) assert.ok(fr[key].length > 3 && en[key].length > 3, key);
});
