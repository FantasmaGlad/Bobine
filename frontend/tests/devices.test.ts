import { test } from "node:test";
import assert from "node:assert/strict";
import { audioKindIcon } from "../src/lib/devices/audio.ts";
import { bluetoothKindIcon, splitBluetooth } from "../src/lib/devices/wireless.ts";
import { type BluetoothDevice } from "../src/lib/devices/types.ts";
import { errorMessage, parseApiError } from "../src/lib/apiError.ts";

test("erreurs de l'API : détail structuré, texte simple ou absent", () => {
  assert.deepEqual(parseApiError(409, { detail: { code: "busy", message: "Occupé", extra_field: 1 } }), {
    status: 409, code: "busy", message: "Occupé", extra: { extra_field: 1 },
  });
  assert.equal(parseApiError(400, { detail: "Message simple" }).message, "Message simple");
  assert.equal(parseApiError(500, null).code, "error");
  const invalid = parseApiError(422, { detail: [{ loc: ["body", "x"], msg: "champ requis" }] });
  assert.equal(invalid.code, "validation_error");
  assert.equal(invalid.message, "champ requis");
  assert.equal(errorMessage({ detail: { code: "external_read_only", message: "Lecture seule" } }, "repli"), "Lecture seule");
  assert.equal(errorMessage(null, "repli"), "repli");
  assert.equal(parseApiError(429, { detail: { code: "timeout", message: "x", retry_after: 60 } }).extra.retry_after, 60);
});

const dev = (over: Partial<BluetoothDevice>): BluetoothDevice => ({
  address: "AA:BB:CC:DD:EE:FF", name: "x", paired: false, connected: false, trusted: false, rssi: null, kind: "other", profiles: [], battery: null, ...over,
});

test("Bluetooth : appairés (connectés d'abord) et à portée triés par signal", () => {
  const { paired, nearby } = splitBluetooth([
    dev({ name: "Zeta", paired: true }),
    dev({ name: "Alpha", paired: true, connected: true }),
    dev({ name: "Loin", rssi: -90 }),
    dev({ name: "Près", rssi: -40 }),
    dev({ name: "Inconnu" }),
  ]);
  assert.deepEqual(paired.map((d) => d.name), ["Alpha", "Zeta"]);
  assert.deepEqual(nearby.map((d) => d.name), ["Près", "Loin", "Inconnu"]);
});

test("icônes des sorties et des appareils", () => {
  assert.equal(audioKindIcon("hdmi"), "settings_input_hdmi");
  assert.equal(audioKindIcon("other"), "volume_up");
  assert.equal(bluetoothKindIcon("headset"), "headset_mic");
  assert.equal(bluetoothKindIcon("???"), "bluetooth");
});

import { audioDisplayName, balanceFromSlider, describeBalance, describeChannels, formatLatency, formatSampleRate, sliderFromBalance } from "../src/lib/devices/audio.ts";

test("détail audio : balance avec cran central, bornes et lecture", () => {
  assert.equal(balanceFromSlider(0), 0);
  assert.equal(balanceFromSlider(3), 0);
  assert.equal(balanceFromSlider(-4), 0);
  assert.equal(balanceFromSlider(-40), -0.4);
  assert.equal(balanceFromSlider(250), 1);
  assert.equal(sliderFromBalance(0.6), 60);
  assert.deepEqual(describeBalance(0), { side: "center", percent: 100 });
  assert.deepEqual(describeBalance(-0.4), { side: "left", percent: 60 });
  assert.deepEqual(describeBalance(1), { side: "right", percent: 0 });
});

test("détail audio : mises en forme", () => {
  assert.equal(formatSampleRate(48000), "48 kHz");
  assert.equal(formatSampleRate(44100), "44.1 kHz");
  assert.equal(formatSampleRate(null), "—");
  assert.equal(formatLatency(21.3), "21.3 ms");
  assert.equal(formatLatency(341.3), "341 ms");
  assert.equal(describeChannels(2, ["FL", "FR"]), "Stéréo (G, D)");
  assert.equal(describeChannels(6, []), "6 canaux");
  assert.equal(describeChannels(1, []), "Mono");
  assert.equal(describeChannels(null, []), "—");
  assert.equal(audioDisplayName({ name: "HDMI", alias: "  Projecteur " }), "Projecteur");
  assert.equal(audioDisplayName({ name: "HDMI", alias: null }), "HDMI");
});
