import { test } from "node:test";
import assert from "node:assert/strict";
import {
  audioKindIcon,
  bluetoothKindIcon,
  isValidPin,
  parseApiError,
  sanitizePin,
  secondsLeft,
  signalBars,
  splitBluetooth,
  wifiConnectPlan,
  type BluetoothDevice,
} from "../src/lib/devicesApi.ts";

test("PIN : six chiffres exactement, saisie nettoyée", () => {
  assert.equal(isValidPin("012345"), true);
  for (const bad of ["12345", "1234567", "12a456", "", " 12345"]) assert.equal(isValidPin(bad), false, bad);
  assert.equal(sanitizePin("12-34 56789"), "123456");
  assert.equal(sanitizePin("abc"), "");
});

test("erreurs de l'API : détail structuré, texte simple ou absent", () => {
  assert.deepEqual(parseApiError(403, { detail: { code: "pin_not_set", message: "Définissez", extra_field: 1 } }), {
    status: 403, code: "pin_not_set", message: "Définissez", extra: { extra_field: 1 },
  });
  assert.equal(parseApiError(400, { detail: "Message simple" }).message, "Message simple");
  assert.equal(parseApiError(500, null).code, "error");
  assert.equal(parseApiError(429, { detail: { code: "locked", message: "x", retry_after: 60 } }).extra.retry_after, 60);
});

test("barres de signal", () => {
  assert.deepEqual([0, 10, 30, 60, 90].map(signalBars), [0, 1, 2, 3, 4]);
});

test("connexion Wi-Fi : le mot de passe ne se saisit qu'en local", () => {
  assert.equal(wifiConnectPlan({ known: true, security: "WPA2" }, false), "direct");
  assert.equal(wifiConnectPlan({ known: false, security: "" }, false), "direct");
  assert.equal(wifiConnectPlan({ known: false, security: "WPA2" }, true), "needs_password");
  assert.equal(wifiConnectPlan({ known: false, security: "WPA2" }, false), "password_local_only");
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

test("icônes et compte à rebours", () => {
  assert.equal(audioKindIcon("hdmi"), "settings_input_hdmi");
  assert.equal(audioKindIcon("other"), "volume_up");
  assert.equal(bluetoothKindIcon("headset"), "headset_mic");
  assert.equal(bluetoothKindIcon("???"), "bluetooth");
  const pending = { kind: "connect" as const, target: "X", previous: "Y", seconds_left: 60 };
  assert.equal(secondsLeft(pending, 12.9), 48);
  assert.equal(secondsLeft(pending, 500), 0);
  assert.equal(secondsLeft(null, 0), 0);
});

import { audioDisplayName, balanceFromSlider, describeBalance, describeChannels, formatLatency, formatSampleRate, sliderFromBalance } from "../src/lib/devicesApi.ts";

test("détail audio : balance avec cran central, bornes et lecture", () => {
  assert.equal(balanceFromSlider(0), 0);
  assert.equal(balanceFromSlider(3), 0); // cran central
  assert.equal(balanceFromSlider(-4), 0);
  assert.equal(balanceFromSlider(-40), -0.4);
  assert.equal(balanceFromSlider(250), 1); // borné
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
