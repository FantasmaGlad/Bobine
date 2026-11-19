import { test } from "node:test";
import assert from "node:assert/strict";
import { formatEta, formatQueueSuffix } from "../src/components/uploads/uploadText.ts";
import { translate } from "../src/lib/i18n/all.ts";

const fr = (k: string, p?: Record<string, string | number>) => translate("fr", k, p);
const en = (k: string, p?: Record<string, string | number>) => translate("en", k, p);

test("le temps restant suit la langue de l'interface", () => {
  assert.equal(formatEta(fr, 42), "~42s restantes");
  assert.equal(formatEta(fr, 125), "~2 min 5s restantes");
  assert.equal(formatEta(fr, 120), "~2 min restantes");
  assert.equal(formatEta(en, 42), "~42s left");
  assert.equal(formatEta(en, 125, "estimate"), "~2 min 5s left (estimate)");
  assert.equal(formatEta(fr, 125, "estimate"), "~2 min 5s restantes (estimation)");
});

test("une durée absente ou invalide ne s'affiche pas", () => {
  assert.equal(formatEta(en, null), null);
  assert.equal(formatEta(en, Number.NaN), null);
  assert.equal(formatEta(en, -1), null);
});

test("la file d'attente annonce les tâches devant et le temps total", () => {
  assert.equal(formatQueueSuffix(fr, 2, 90), " (2 devant, ~1 min 30s au total)");
  assert.equal(formatQueueSuffix(en, 2, 90), " (2 ahead, ~1 min 30s in total)");
  assert.equal(formatQueueSuffix(en, 1, null), " (1 ahead)");
  assert.equal(formatQueueSuffix(en, 0, 90), "");
});
