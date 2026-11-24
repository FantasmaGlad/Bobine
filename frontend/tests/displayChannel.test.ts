import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildOutputUrl,
  createPageClientId,
  isLoopbackHost,
  parseChannelParam,
  resolveChannel,
  screenUrl,
  shouldFollowInitialOutput,
} from "../src/lib/displayChannel.ts";

test("le paramètre explicite l'emporte sur tout, y compris en 127.0.0.1", () => {
  assert.deepEqual(resolveChannel("?output=network", "127.0.0.1", "kiosk"), { channel: "network", source: "query" });
  assert.deepEqual(resolveChannel("?output=network", "127.0.0.1", "cinema"), { channel: "network", source: "query" });
  assert.deepEqual(resolveChannel("?output=cable", "192.168.1.20", "cinema"), { channel: "cable", source: "query" });
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

test("valeur invalide ou ancien ?channel= ignoré", () => {
  assert.equal(parseChannelParam("?output=radio"), null);
  assert.equal(parseChannelParam("?channel=network"), null);
  assert.equal(parseChannelParam("?channel=cable"), null);
  assert.equal(parseChannelParam(""), null);
  assert.equal(resolveChannel("?output=nimporte", "192.168.1.20", "cinema").channel, "network");
  assert.equal(resolveChannel("?channel=network", "127.0.0.1", "kiosk").channel, "cable");
});

test("la redirection conserve le canal et le reste de la query", () => {
  assert.equal(buildOutputUrl("cinema", "?output=network", "network"), "/cinema?output=network");
  assert.equal(buildOutputUrl("kiosk", "", "network"), "/kiosk?output=network");
  assert.equal(buildOutputUrl("kiosk", "?debug=sync", "cable"), "/kiosk?debug=sync&output=cable");
});

test("scénario d'origine : écran réseau en 127.0.0.1 reste réseau après redirection kiosk -> cinéma -> kiosk", () => {
  const first = resolveChannel("?output=network", "127.0.0.1", "kiosk");
  const toCinema = buildOutputUrl("cinema", "?output=network", first.channel);
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

import { decideOutputRedirect, radioChannelId } from "../src/lib/displayChannel.ts";

test("radio : /radio nu = Réseau 2, l'ancienne radio réseau, quel que soit l'hôte (compatibilité des favoris)", () => {
  assert.deepEqual(resolveChannel("", "127.0.0.1", "radio"), { channel: "network_2", source: "default" });
  assert.deepEqual(resolveChannel("", "192.168.1.20", "radio"), { channel: "network_2", source: "default" });
  assert.deepEqual(resolveChannel("", "bobine.local", "radio"), { channel: "network_2", source: "default" });
});

test("radio : la sortie explicite l'emporte ; seul ?output= est lu", () => {
  assert.deepEqual(resolveChannel("?output=cable", "127.0.0.1", "radio"), { channel: "cable", source: "query" });
  assert.deepEqual(resolveChannel("?output=cable", "192.168.1.20", "radio"), { channel: "cable", source: "query" });
  assert.deepEqual(resolveChannel("?output=network", "127.0.0.1", "radio"), { channel: "network", source: "query" });
  assert.deepEqual(resolveChannel("?channel=cable", "127.0.0.1", "radio"), { channel: "network_2", source: "default" });
  assert.deepEqual(resolveChannel("?output=network", "192.168.1.20", "kiosk"), { channel: "network", source: "query" });
});

test("radio : identifiant du moteur serveur selon la sortie", () => {
  assert.equal(radioChannelId("cable"), "radio_cable");
  assert.equal(radioChannelId("network"), "radio_network");
});

test("radio : la redirection vers la radio câblée conserve la requête et pose le canal", () => {
  assert.equal(buildOutputUrl("radio", "", "cable"), "/radio?output=cable");
  assert.equal(buildOutputUrl("radio", "?output=cable", "cable"), "/radio?output=cable");
  assert.equal(buildOutputUrl("radio", "?debug=1", "cable"), "/radio?debug=1&output=cable");
});

test("radio : la page radio ne suit jamais la sortie stockée au montage", () => {
  assert.equal(shouldFollowInitialOutput("cable", "radio"), false);
  assert.equal(shouldFollowInitialOutput("network", "radio"), false);
  assert.equal(shouldFollowInitialOutput("cable"), true);
  assert.equal(shouldFollowInitialOutput("cable", "kiosk"), true);
});

test("redirection : le kiosque de la machine passe sur la radio câblée dès le montage", () => {
  const d = decideOutputRedirect("kiosk", "", "127.0.0.1", { cable: "radio", network: "kiosk" }, null);
  assert.equal(d.to, "/radio?output=cable");
  assert.equal(d.seen, "radio");
});

test("redirection : /cinema?output=cable (HDMI Android) suit aussi la radio, requête conservée", () => {
  const d = decideOutputRedirect("cinema", "?output=cable", "127.0.0.1", { cable: "radio", network: "kiosk" }, null);
  assert.equal(d.to, "/radio?output=cable");
});

test("redirection : un écran réseau suit sa propre sortie vers la radio, jamais celle du câble", () => {
  assert.equal(decideOutputRedirect("kiosk", "?output=network", "127.0.0.1", { cable: "radio", network: "cinema" }, null).to, null);
  assert.equal(decideOutputRedirect("kiosk", "?output=network", "127.0.0.1", { cable: "kiosk", network: "radio" }, null).to, null);
  assert.equal(decideOutputRedirect("cinema", "?output=network", "192.168.1.20", { cable: "kiosk", network: "radio" }, "kiosk").to, "/radio?output=network");
});

test("redirection : la radio câblée repart sur une bascule faite en direct, pas au montage", () => {
  const mount = decideOutputRedirect("radio", "?output=cable", "127.0.0.1", { cable: "radio", network: "kiosk" }, null);
  assert.equal(mount.to, null);
  assert.equal(mount.seen, "radio");
  const live = decideOutputRedirect("radio", "?output=cable", "127.0.0.1", { cable: "cinema", network: "kiosk" }, mount.seen);
  assert.equal(live.to, "/cinema?output=cable");
  const liveKiosk = decideOutputRedirect("radio", "?output=cable", "127.0.0.1", { cable: "kiosk", network: "kiosk" }, "radio");
  assert.equal(liveKiosk.to, "/kiosk?output=cable");
});

test("redirection : /radio?output=cable ouvert à la main hors sortie radio n'est pas éjecté", () => {
  const mount = decideOutputRedirect("radio", "?output=cable", "192.168.1.20", { cable: "kiosk", network: "kiosk" }, null);
  assert.equal(mount.to, null);
  assert.equal(decideOutputRedirect("radio", "?output=cable", "192.168.1.20", { cable: "cinema", network: "kiosk" }, mount.seen).to, null);
  const inSync = decideOutputRedirect("radio", "?output=cable", "192.168.1.20", { cable: "radio", network: "kiosk" }, "cinema");
  assert.equal(inSync.to, null);
  assert.equal(decideOutputRedirect("radio", "?output=cable", "192.168.1.20", { cable: "kiosk", network: "kiosk" }, inSync.seen).to, "/kiosk?output=cable");
});

test("redirection : un poste radio réseau (ou /radio nu) ne suit jamais aucune sortie", () => {
  for (const search of ["", "?output=network_2"]) {
    assert.equal(decideOutputRedirect("radio", search, "192.168.1.20", { cable: "cinema", network: "cinema" }, "radio").to, null);
    assert.equal(decideOutputRedirect("radio", search, "127.0.0.1", { cable: "kiosk", network: "kiosk" }, "radio").to, null);
  }
});

test("redirection : comportement historique kiosk <-> cinéma inchangé", () => {
  assert.equal(decideOutputRedirect("kiosk", "", "127.0.0.1", { cable: "cinema", network: "kiosk" }, null).to, "/cinema?output=cable");
  assert.equal(decideOutputRedirect("cinema", "?output=network", "192.168.1.20", { cable: "kiosk", network: "kiosk" }, null).to, null);
  assert.equal(decideOutputRedirect("cinema", "?output=network", "192.168.1.20", { cable: "kiosk", network: "kiosk" }, "cinema").to, "/kiosk?output=network");
});

test("un changement de sortie de l'AUTRE canal ne fait jamais naviguer un écran (canaux indépendants)", async () => {
  const { decideOutputRedirect, shouldEvaluateRedirect } = await import("../src/lib/displayChannel.ts");
  const search = "?output=network";
  const first = decideOutputRedirect("kiosk", search, "192.168.1.50", { cable: "kiosk", network: "cinema" }, null);
  assert.equal(first.to, null);
  assert.equal(shouldEvaluateRedirect("network", { cable: "cinema", network: "cinema" }, first.seen), false);
  const buggy = decideOutputRedirect("kiosk", search, "192.168.1.50", { cable: "cinema", network: "cinema" }, first.seen);
  assert.notEqual(buggy.to, null);
  assert.equal(shouldEvaluateRedirect("network", { cable: "kiosk", network: "kiosk" }, first.seen), true);
  const real = decideOutputRedirect("kiosk", search, "192.168.1.50", { cable: "kiosk", network: "kiosk" }, first.seen);
  assert.equal(real.to, null);
  const toCinema = decideOutputRedirect("kiosk", search, "192.168.1.50", { cable: "kiosk", network: "cinema" }, "kiosk");
  assert.equal(toCinema.to, "/cinema?output=network");
  assert.equal(shouldEvaluateRedirect("cable", { cable: "cinema", network: null }, null), true);
  assert.equal(shouldEvaluateRedirect("cable", { cable: null, network: "cinema" }, null), false);
});

test("le bouton d'ouverture mène à l'adresse unique de la sortie", () => {
  assert.equal(screenUrl("cable"), "/screen?output=cable");
  assert.equal(screenUrl("network_2"), "/screen?output=network_2");
});

test("l'adresse unique ouvre l'écran du mode courant de sa sortie", async () => {
  const { screenOutput, screenTarget } = await import("../src/lib/displayChannel.ts");
  assert.equal(screenOutput("?output=network_2"), "network_2");
  assert.equal(screenOutput("?channel=network"), "cable");
  assert.equal(screenOutput(""), "cable");
  assert.equal(screenTarget("?output=network_2", "radio"), "/radio?output=network_2");
  assert.equal(screenTarget("?output=network&zoom=1", "signage"), "/signage?output=network&zoom=1");
  assert.equal(screenTarget("?output=cable", "inconnu"), null);
  assert.equal(screenTarget("?output=cable", undefined), null);
});

import { lockedOutput, outputsFor, parseDisplayOutput } from "../src/lib/displayChannel.ts";

test("chaque sortie offre les mêmes modes, radio comprise", () => {
  for (const output of ["cable", "network", "network_2"] as const) assert.deepEqual(outputsFor(output), ["kiosk", "cinema", "radio", "signage"]);
  assert.equal(parseDisplayOutput("network", "signage"), "signage");
  assert.equal(parseDisplayOutput("network", "radio"), "radio");
  assert.equal(parseDisplayOutput("cable", "autre"), null);
});

test("visuel : le motif du verrou nomme la sortie qui l'impose", () => {
  assert.equal(lockedOutput("signage_locked"), "signage");
  assert.equal(lockedOutput("radio_locked"), "radio");
  assert.equal(lockedOutput("kiosk_locked"), null);
  assert.equal(lockedOutput("coach_cable_only"), null);
});

test("visuel : le kiosque câblé passe sur /signage et la page du visuel revient au kiosque", () => {
  const toSignage = decideOutputRedirect("kiosk", "", "127.0.0.1", { cable: "signage", network: null }, "kiosk");
  assert.equal(toSignage.to, "/signage?output=cable");
  const back = decideOutputRedirect("signage", "?output=network", "192.0.2.5", { cable: null, network: "kiosk" }, "signage");
  assert.equal(back.to, "/kiosk?output=network");
});

test("Réseau 2 suit sa propre sortie, jamais celle de Réseau 1", async () => {
  const { decideOutputRedirect, parseDisplayOutputs, radioChannelId, parseChannelParam } = await import("../src/lib/displayChannel.ts");
  const search = "?output=network_2";
  assert.equal(parseChannelParam(search), "network_2");
  assert.equal(decideOutputRedirect("kiosk", search, "192.0.2.7", { network: "cinema", network_2: "kiosk" }, "kiosk").to, null);
  assert.equal(decideOutputRedirect("kiosk", search, "192.0.2.7", { network: "kiosk", network_2: "cinema" }, "kiosk").to, "/cinema?output=network_2");
  const listed = [{ id: "cable", mode: "radio" }, { id: "network", mode: "signage" }, { id: "network_2", mode: "radio" }];
  assert.deepEqual(parseDisplayOutputs(listed, { network: "kiosk" }),
    { cable: "radio", network: "kiosk", network_2: "radio" });
  assert.equal(radioChannelId("network_2"), "radio_network_2");
});
