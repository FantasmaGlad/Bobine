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

// --- Sortie radio (version 5.0.1) ------------------------------------------------
import { decideOutputRedirect, radioChannelId } from "../src/lib/displayChannel.ts";

test("radio : /radio nu = réseau quel que soit l'hôte (compatibilité des favoris)", () => {
  assert.deepEqual(resolveChannel("", "127.0.0.1", "radio"), { channel: "network", source: "default" });
  assert.deepEqual(resolveChannel("", "192.168.1.20", "radio"), { channel: "network", source: "default" });
  assert.deepEqual(resolveChannel("", "bobine.local", "radio"), { channel: "network", source: "default" });
});

test("radio : ?channel= explicite l'emporte, y compris câblé en 127.0.0.1 ou sur le LAN", () => {
  assert.deepEqual(resolveChannel("?channel=cable", "127.0.0.1", "radio"), { channel: "cable", source: "query" });
  assert.deepEqual(resolveChannel("?channel=cable", "192.168.1.20", "radio"), { channel: "cable", source: "query" });
  assert.deepEqual(resolveChannel("?channel=network", "127.0.0.1", "radio"), { channel: "network", source: "query" });
});

test("radio : identifiant du moteur serveur selon la sortie", () => {
  assert.equal(radioChannelId("cable"), "radio_cable");
  assert.equal(radioChannelId("network"), "radio_network");
});

test("radio : la redirection vers la radio câblée conserve la requête et pose le canal", () => {
  assert.equal(buildOutputUrl("radio", "", "cable"), "/radio?channel=cable");
  assert.equal(buildOutputUrl("radio", "?channel=cable", "cable"), "/radio?channel=cable");
  assert.equal(buildOutputUrl("radio", "?debug=1", "cable"), "/radio?debug=1&channel=cable");
});

test("radio : la page radio ne suit jamais la sortie stockée au montage", () => {
  assert.equal(shouldFollowInitialOutput("cable", "radio"), false);
  assert.equal(shouldFollowInitialOutput("network", "radio"), false);
  assert.equal(shouldFollowInitialOutput("cable"), true);
  assert.equal(shouldFollowInitialOutput("cable", "kiosk"), true);
});

test("redirection : le kiosque du Wyse passe sur la radio câblée dès le montage", () => {
  // /kiosk (câblé par défaut), sortie câblée stockée = radio, valeur initiale.
  const d = decideOutputRedirect("kiosk", "", "127.0.0.1", "radio", "kiosk", null);
  assert.equal(d.to, "/radio?channel=cable");
  assert.equal(d.seen, "radio");
});

test("redirection : /cinema?channel=cable (HDMI Android) suit aussi la radio, requête conservée", () => {
  const d = decideOutputRedirect("cinema", "?channel=cable", "127.0.0.1", "radio", "kiosk", null);
  assert.equal(d.to, "/radio?channel=cable");
});

test("redirection : un écran réseau ne bascule jamais vers la radio", () => {
  assert.equal(decideOutputRedirect("kiosk", "?channel=network", "127.0.0.1", "radio", "cinema", null).to, null);
  // Même si, par erreur, le serveur annonçait « radio » pour le réseau.
  assert.equal(decideOutputRedirect("kiosk", "?channel=network", "127.0.0.1", "kiosk", "radio", null).to, null);
  assert.equal(decideOutputRedirect("cinema", "?channel=network", "192.168.1.20", "kiosk", "radio", "kiosk").to, null);
});

test("redirection : la radio câblée repart sur une bascule faite en direct, pas au montage", () => {
  // Montage alors que la sortie est radio : on y reste.
  const mount = decideOutputRedirect("radio", "?channel=cable", "127.0.0.1", "radio", "kiosk", null);
  assert.equal(mount.to, null);
  assert.equal(mount.seen, "radio");
  // L'admin repasse en cinéma : la page repart, requête et canal conservés.
  const live = decideOutputRedirect("radio", "?channel=cable", "127.0.0.1", "cinema", "kiosk", mount.seen);
  assert.equal(live.to, "/cinema?channel=cable");
  const liveKiosk = decideOutputRedirect("radio", "?channel=cable", "127.0.0.1", "kiosk", "kiosk", "radio");
  assert.equal(liveKiosk.to, "/kiosk?channel=cable");
});

test("redirection : /radio?channel=cable ouvert à la main hors sortie radio n'est pas éjecté", () => {
  // Sortie câblée en kiosk au montage : on reste.
  const mount = decideOutputRedirect("radio", "?channel=cable", "192.168.1.20", "kiosk", "kiosk", null);
  assert.equal(mount.to, null);
  // L'admin passe kiosk -> cinéma : cette page n'était pas « en phase » radio, elle reste.
  assert.equal(decideOutputRedirect("radio", "?channel=cable", "192.168.1.20", "cinema", "kiosk", mount.seen).to, null);
  // Puis l'admin bascule sur radio (on est déjà sur la bonne page) puis repart : là on suit.
  const inSync = decideOutputRedirect("radio", "?channel=cable", "192.168.1.20", "radio", "kiosk", "cinema");
  assert.equal(inSync.to, null);
  assert.equal(decideOutputRedirect("radio", "?channel=cable", "192.168.1.20", "kiosk", "kiosk", inSync.seen).to, "/kiosk?channel=cable");
});

test("redirection : un poste radio réseau (ou /radio nu) ne suit jamais aucune sortie", () => {
  for (const search of ["", "?channel=network"]) {
    assert.equal(decideOutputRedirect("radio", search, "192.168.1.20", "cinema", "cinema", "radio").to, null);
    assert.equal(decideOutputRedirect("radio", search, "127.0.0.1", "kiosk", "kiosk", "radio").to, null);
  }
});

test("redirection : comportement historique kiosk <-> cinéma inchangé", () => {
  assert.equal(decideOutputRedirect("kiosk", "", "127.0.0.1", "cinema", "kiosk", null).to, "/cinema?channel=cable");
  // Écran réseau : pas de redirection à la valeur initiale, suivi des bascules en direct.
  assert.equal(decideOutputRedirect("cinema", "?channel=network", "192.168.1.20", "kiosk", "kiosk", null).to, null);
  assert.equal(decideOutputRedirect("cinema", "?channel=network", "192.168.1.20", "kiosk", "kiosk", "cinema").to, "/kiosk?channel=network");
});
