import { test } from "node:test";
import assert from "node:assert/strict";
import { chapterJumpTarget, chapterToastPlacement, type Chapter } from "../src/lib/chapters.ts";

const chapters: Chapter[] = [
  { id: 1, position: 0, start_seconds: 0, end_seconds: 60, title: "Échauffement" },
  { id: 2, position: 1, start_seconds: 60, end_seconds: 300, title: "Bloc 1" },
  { id: 3, position: 2, start_seconds: 300, end_seconds: null, title: "Retour au calme" },
];

test("chapitre suivant, rien après le dernier", () => {
  assert.equal(chapterJumpTarget(chapters, 10, "next"), 60);
  assert.equal(chapterJumpTarget(chapters, 120, "next"), 300);
  assert.equal(chapterJumpTarget(chapters, 320, "next"), null);
});

test("précédent : début du chapitre en cours, puis chapitre d'avant", () => {
  assert.equal(chapterJumpTarget(chapters, 120, "prev"), 60);
  assert.equal(chapterJumpTarget(chapters, 61, "prev"), 0);
  assert.equal(chapterJumpTarget(chapters, 1, "prev"), 0);
});

test("sans chapitre, aucun saut", () => {
  assert.equal(chapterJumpTarget([], 50, "next"), null);
});

test("bandeau de chapitre masqué tant que l'aperçu de la timeline, qui porte le titre, est affiché", () => {
  assert.equal(chapterToastPlacement({ previewing: true, controlsVisible: false }), "hidden");
  assert.equal(chapterToastPlacement({ previewing: true, controlsVisible: true }), "hidden");
});

test("bandeau de chapitre levé au-dessus des commandes, en bas sinon", () => {
  assert.equal(chapterToastPlacement({ previewing: false, controlsVisible: true }), "lifted");
  assert.equal(chapterToastPlacement({ previewing: false, controlsVisible: false }), "rest");
});
