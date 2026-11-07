import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { SETTINGS_CATEGORIES, categoryOfSection, matchCategories, normalizeSearch } from "../src/lib/settingsCategories.ts";

test("chaque section appartient à une seule catégorie", () => {
  const seen = new Map<string, string>();
  for (const category of SETTINGS_CATEGORIES) {
    for (const section of category.sections) {
      assert.equal(seen.has(section), false, `${section} dans deux catégories`);
      seen.set(section, category.id);
      assert.equal(categoryOfSection(section), category.id);
    }
  }
  assert.equal(categoryOfSection("inconnue"), undefined);
});

test("toutes les sections de la page Réglages sont rangées, et inversement", () => {
  const page = readFileSync(new URL("../src/app/settings/page.tsx", import.meta.url), "utf8");
  // Chaque bloc de la page porte son identifiant et sa visibilité par catégorie : id="x" hidden={!shows("x")}.
  const ids = [...page.matchAll(/\bid="([\w-]+)" hidden=\{!shows\("([\w-]+)"\)\}/g)].map((m) => {
    assert.equal(m[1], m[2], `${m[1]} : identifiant et shows() différents`);
    return m[1];
  });
  const declared = SETTINGS_CATEGORIES.flatMap((category) => [...category.sections]);
  assert.deepEqual([...ids].sort(), [...declared].sort());
});

test("recherche : insensible aux accents et à la casse, tous les mots exigés", () => {
  const text: Record<string, string> = { appearance: "Apparence thème mode clair sombre langue logo", display: "Affichage écran HDMI projecteur" };
  const haystack = (id: string) => text[id] ?? "";
  assert.deepEqual([...matchCategories("ECRAN", haystack)], ["display"]);
  assert.deepEqual([...matchCategories("theme sombre", haystack)], ["appearance"]);
  assert.deepEqual([...matchCategories("theme hdmi", haystack)], []);
  assert.equal(matchCategories("   ", haystack).size, 0);
  assert.equal(normalizeSearch("  Écran Câblé "), "ecran cable");
});
