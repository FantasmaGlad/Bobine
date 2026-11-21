import assert from "node:assert/strict";
import test from "node:test";

import { logoNeedsReload, sameNetwork } from "../src/lib/settings/apply.ts";

const network = { localIp: "10.0.0.2", port: 1903, mdnsUrl: "http://bobine.local:1903" };

test("une relecture sans changement ne recharge pas le logo", () => {
  assert.equal(logoNeedsReload(true, { hasCustomLogo: true }), false);
  assert.equal(logoNeedsReload(false, {}), false);
});

test("un logo poussé, ajouté ou retiré est rechargé", () => {
  assert.equal(logoNeedsReload(true, { hasCustomLogo: true, logoChanged: true }), true);
  assert.equal(logoNeedsReload(false, { hasCustomLogo: true }), true);
  assert.equal(logoNeedsReload(true, { hasCustomLogo: false }), true);
});

test("une adresse réseau identique est reconnue comme la même", () => {
  assert.equal(sameNetwork(network, { ...network }), true);
  assert.equal(sameNetwork(network, { ...network, localIp: "10.0.0.3" }), false);
});
