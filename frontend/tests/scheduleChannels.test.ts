import { test } from "node:test";
import assert from "node:assert/strict";
import { isRadioLane, parseScheduleChannel } from "../src/lib/scheduleChannels.ts";

test("les quatre voies sont reconnues telles quelles", () => {
  for (const channel of ["cable", "network", "radio_cable", "radio_network"] as const) {
    assert.equal(parseScheduleChannel(channel), channel);
  }
});

test("l'ancien lien ?channel=radio ouvre la voie radio réseau", () => {
  assert.equal(parseScheduleChannel("radio"), "radio_network");
});

test("valeur absente ou inconnue : câblé, comme avant", () => {
  assert.equal(parseScheduleChannel(null), "cable");
  assert.equal(parseScheduleChannel(undefined), "cable");
  assert.equal(parseScheduleChannel(""), "cable");
  assert.equal(parseScheduleChannel("zzz"), "cable");
});

test("seules les deux voies radio sont des voies radio", () => {
  assert.equal(isRadioLane("radio_cable"), true);
  assert.equal(isRadioLane("radio_network"), true);
  assert.equal(isRadioLane("cable"), false);
  assert.equal(isRadioLane("network"), false);
});
