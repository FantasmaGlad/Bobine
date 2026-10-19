import { test } from "node:test";
import assert from "node:assert/strict";
import {
  highlightSegments,
  matchesQuery,
  normalizeText,
  queryTokens,
  rankByQuery,
  scoreMatch,
  suggestFrom,
} from "../src/lib/searchText.ts";

test("normalisation : casse, accents et espaces ignorés", () => {
  assert.equal(normalizeText("  Été   À  Suivre "), "ete a suivre");
  assert.equal(normalizeText("Beyoncé"), "beyonce");
});

test("tous les mots doivent correspondre, dans n'importe quel ordre", () => {
  assert.equal(matchesQuery("Rpm 101 — Cycling", "cycling rpm"), true);
  assert.equal(matchesQuery("Rpm 101 — Cycling", "rpm yoga"), false);
  assert.equal(matchesQuery("Été indien", "ete"), true);
  assert.equal(matchesQuery("Quoi que ce soit", ""), true);
  assert.equal(matchesQuery("Quoi que ce soit", "   "), true);
});

test("mots de la requête uniques et normalisés", () => {
  assert.deepEqual(queryTokens("Bass  bass BOOST"), ["bass", "boost"]);
  assert.deepEqual(queryTokens(""), []);
});

test("le début de texte l'emporte sur le début de mot, lui-même sur l'inclusion", () => {
  const start = scoreMatch("Bass Boost", "bass");
  const word = scoreMatch("Sub bass line", "bass");
  const inside = scoreMatch("Contrebasse", "bass");
  assert.ok(start > word && word > inside && inside > 0);
  assert.equal(scoreMatch("Rien", "bass"), 0);
});

test("classement : pertinence puis ordre d'origine ; non-correspondances écartées", () => {
  const items = ["Contrebasse", "Sub bass line", "Bass Boost", "Voix", "Basse noire"];
  assert.deepEqual(rankByQuery(items, "bass", (x) => x), ["Bass Boost", "Basse noire", "Sub bass line", "Contrebasse"]);
  assert.deepEqual(rankByQuery(items, "", (x) => x), items);
  assert.deepEqual(rankByQuery(items, "zzz", (x) => x), []);
});

test("suggestions : uniques, classées, sans la saisie exacte, bornées", () => {
  const pool = ["Daft Punk", "daft punk", "Daft Club", "Punk Rock", "Autre"];
  assert.deepEqual(suggestFrom(pool, "daft", 5), ["Daft Punk", "Daft Club"]);
  assert.deepEqual(suggestFrom(pool, "daft punk", 5), []);
  assert.deepEqual(suggestFrom(pool, "", 5), []);
  assert.equal(suggestFrom(["a1", "a2", "a3", "a4"], "a", 2).length, 2);
  assert.deepEqual(suggestFrom(pool, "punk"), ["Punk Rock", "Daft Punk"]);
});

test("surlignage : texte d'origine conservé, accents et casse tolérés", () => {
  const segs = highlightSegments("Été Indien", "ete");
  assert.deepEqual(segs, [{ text: "Été", match: true }, { text: " Indien", match: false }]);
  assert.equal(segs.map((s) => s.text).join(""), "Été Indien");
  const multi = highlightSegments("Bass Boost bass", "bass");
  assert.deepEqual(multi.filter((s) => s.match).map((s) => s.text), ["Bass", "bass"]);
  assert.deepEqual(highlightSegments("Rien", "zzz"), [{ text: "Rien", match: false }]);
  assert.deepEqual(highlightSegments("Rien", ""), [{ text: "Rien", match: false }]);
  assert.deepEqual(highlightSegments("", "a"), [{ text: "", match: false }]);
});
