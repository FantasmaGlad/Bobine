import { test } from "node:test";
import assert from "node:assert/strict";
import { oneOf, readUrlView, withUrlView } from "../src/lib/urlView.ts";

const VIEWS = oneOf(["media", "playlists"] as const, "media");

test("la vue de l'URL est lue si elle est connue, sinon la vue par défaut", () => {
  assert.equal(readUrlView("?vue=playlists", "vue", VIEWS), "playlists");
  assert.equal(readUrlView("?vue=inconnue", "vue", VIEWS), "media");
  assert.equal(readUrlView("", "vue", VIEWS), "media");
});

test("la vue par défaut n'encombre pas l'URL et les autres paramètres restent", () => {
  assert.equal(withUrlView("?vue=playlists&q=x", "vue", "media", "media"), "?q=x");
  assert.equal(withUrlView("", "vue", "playlists", "media"), "?vue=playlists");
  assert.equal(withUrlView("?vue=media", "vue", "media", "media"), "");
});
