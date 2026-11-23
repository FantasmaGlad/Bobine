import { test } from "node:test";
import assert from "node:assert/strict";
import { occurrencesPath, upcomingOnly } from "../src/lib/upcoming.ts";

test("les occurrences annulées sont écartées et la liste est bornée", () => {
  const list = [{ override_action: "cancelled", id: 1 }, { override_action: null, id: 2 }, { override_action: "replaced", id: 3 }, { override_action: null, id: 4 }];
  assert.deepEqual(upcomingOnly(list, 2).map((o) => o.id), [2, 3]);
});

test("la fenêtre demandée part de maintenant", () => {
  const path = occurrencesPath("cable", new Date("2026-11-23T10:00:00Z"), 1);
  assert.equal(path, "/schedule/occurrences?start=2026-11-23T10:00:00.000Z&end=2026-11-24T10:00:00.000Z&channel=cable");
});
