import { test } from "node:test";
import assert from "node:assert/strict";
import { SCHEDULE_CHANNELS, parseScheduleChannel } from "../src/lib/scheduleChannels.ts";

test("une ligne de planning par sortie, reconnue telle quelle", () => {
  assert.deepEqual(SCHEDULE_CHANNELS, ["cable", "network", "network_2"]);
  for (const channel of SCHEDULE_CHANNELS) assert.equal(parseScheduleChannel(channel), channel);
});

test("un ancien lien de voie radio ouvre la ligne de sa sortie", () => {
  assert.equal(parseScheduleChannel("radio_cable"), "cable");
  assert.equal(parseScheduleChannel("radio_network"), "network");
  assert.equal(parseScheduleChannel("radio_network_2"), "network_2");
  assert.equal(parseScheduleChannel("radio"), "network_2");
});

test("valeur absente ou inconnue : câblé, comme avant", () => {
  assert.equal(parseScheduleChannel(null), "cable");
  assert.equal(parseScheduleChannel(undefined), "cable");
  assert.equal(parseScheduleChannel(""), "cable");
  assert.equal(parseScheduleChannel("zzz"), "cable");
});
