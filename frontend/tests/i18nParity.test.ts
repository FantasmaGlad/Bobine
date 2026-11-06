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

test("toute clé littérale utilisée par t(\"...\") existe dans le dictionnaire", async () => {
  const { readdirSync, readFileSync, statSync } = await import("node:fs");
  const { join } = await import("node:path");
  const { lookupPath } = await import("../src/lib/i18n/core.ts");
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (/\.(ts|tsx)$/.test(name) && !path.includes(`${"/"}i18n${"/"}`)) files.push(path);
    }
  };
  walk(join(import.meta.dirname, "..", "src"));
  const missing: string[] = [];
  for (const file of files) {
    for (const match of readFileSync(file, "utf8").matchAll(/\bt(?:List)?\(\s*"([A-Za-z0-9_.]+)"/g)) {
      if (lookupPath(dictionaries.fr, match[1]) === undefined) missing.push(`${file.split("/src/")[1]} : ${match[1]}`);
    }
  }
  assert.deepEqual(missing, [], "clés utilisées mais absentes de fr.ts");
});
