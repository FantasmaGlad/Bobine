import assert from "node:assert/strict";
import { test } from "node:test";

import { dictionaries } from "../src/lib/i18n/all.ts";
import type { Dict } from "../src/lib/i18n/core.ts";

// Un export ne contient qu'une langue : aucune clé ne peut plus retomber sur l'autre.
function leaves(dict: Dict, prefix = ""): Map<string, string | string[]> {
  const out = new Map<string, string | string[]>();
  for (const [key, value] of Object.entries(dict)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string" || Array.isArray(value)) out.set(path, value);
    else for (const [subPath, subValue] of leaves(value, path)) out.set(subPath, subValue);
  }
  return out;
}

const placeholders = (value: string | string[]) =>
  (Array.isArray(value) ? value.join("\n") : value).match(/\{\{\w+\}\}/g)?.sort().join(",") ?? "";

test("le français et l'anglais ont exactement les mêmes clés", () => {
  const fr = leaves(dictionaries.fr);
  const en = leaves(dictionaries.en);
  const missingEn = [...fr.keys()].filter((key) => !en.has(key));
  const missingFr = [...en.keys()].filter((key) => !fr.has(key));
  assert.deepEqual(missingEn, [], "clés absentes de en.ts");
  assert.deepEqual(missingFr, [], "clés absentes de fr.ts");
});

test("mêmes paramètres {{...}} et mêmes longueurs de liste dans les deux langues", () => {
  const fr = leaves(dictionaries.fr);
  const en = leaves(dictionaries.en);
  for (const [key, value] of fr) {
    const other = en.get(key);
    if (other === undefined) continue;
    assert.equal(placeholders(other), placeholders(value), `paramètres différents : ${key}`);
    assert.equal(Array.isArray(other), Array.isArray(value), `type différent : ${key}`);
    if (Array.isArray(value) && Array.isArray(other)) assert.equal(other.length, value.length, `liste différente : ${key}`);
  }
});
