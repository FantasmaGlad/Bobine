import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildOutputUrl,
  createPageClientId,
  isLoopbackHost,
  parseChannelParam,
  resolveChannel,
  shouldFollowInitialOutput,
} from "../src/lib/displayChannel.ts";

test("le paramètre explicite l'emporte sur tout, y compris en 127.0.0.1", () => {
  assert.deepEqual(resolveChannel("?channel=network", "127.0.0.1", "kiosk"), { channel: "network", source: "query" });
  assert.deepEqual(resolveChannel("?channel=network", "127.0.0.1", "cinema"), { channel: "network", source: "query" });
  assert.deepEqual(resolveChannel("?channel=cable", "192.168.1.20", "cinema"), { channel: "cable", source: "query" });
});

test("défaut kiosk = câblé même sur une IP LAN (décision 675e441)", () => {
  assert.equal(resolveChannel("", "192.168.1.20", "kiosk").channel, "cable");
});

test("défaut cinéma = heuristique sur le nom d'hôte", () => {
  assert.equal(resolveChannel("", "127.0.0.1", "cinema").channel, "cable");
  assert.equal(resolveChannel("", "localhost", "cinema").channel, "cable");
  assert.equal(resolveChannel("", "192.168.1.20", "cinema").channel, "network");
  assert.equal(resolveChannel("", "bobine.local", "cinema").channel, "network");
});

test("valeur de paramètre invalide ignorée", () => {
  assert.equal(parseChannelParam("?channel=radio"), null);
  assert.equal(parseChannelParam(""), null);
  assert.equal(resolveChannel("?channel=nimporte", "192.168.1.20", "cinema").channel, "network");
});

test("la redirection conserve le canal et le reste de la query", () => {
  assert.equal(buildOutputUrl("cinema", "?channel=network", "network"), "/cinema?channel=network");
  assert.equal(buildOutputUrl("kiosk", "", "network"), "/kiosk?channel=network");
  assert.equal(buildOutputUrl("kiosk", "?debug=sync", "cable"), "/kiosk?debug=sync&channel=cable");
});

test("scénario d'origine : écran réseau en 127.0.0.1 reste réseau après redirection kiosk -> cinéma -> kiosk", () => {
  const first = resolveChannel("?channel=network", "127.0.0.1", "kiosk");
  const toCinema = buildOutputUrl("cinema", "?channel=network", first.channel);
  const search = toCinema.slice(toCinema.indexOf("?"));
  assert.equal(resolveChannel(search, "127.0.0.1", "cinema").channel, "network");
  const back = buildOutputUrl("kiosk", search, "network");
  assert.equal(resolveChannel(back.slice(back.indexOf("?")), "127.0.0.1", "kiosk").channel, "network");
});

test("seul le canal câblé suit la sortie stockée au montage", () => {
  assert.equal(shouldFollowInitialOutput("cable"), true);
  assert.equal(shouldFollowInitialOutput("network"), false);
});

test("hôtes de la boucle locale", () => {
  for (const h of ["127.0.0.1", "localhost", "[::1]", "::1"]) assert.equal(isLoopbackHost(h), true);
  for (const h of ["192.168.1.20", "bobine.local", "127.0.0.2"]) assert.equal(isLoopbackHost(h), false);
});

test("deux chargements de page = deux identifiants distincts", () => {
  assert.notEqual(createPageClientId(), createPageClientId());
  assert.equal(createPageClientId(() => "abc"), "kiosk-abc");
});
