import { test } from "node:test";
import assert from "node:assert/strict";
import { activeChildHref } from "../src/components/layout/navActive.ts";
import { isNavGroup, navEntries, visibleNavEntries } from "../src/lib/navLinks.ts";

const library = navEntries.find((entry) => isNavGroup(entry) && entry.groupKey === "nav.libraryGroup");

test("dans un groupe, seul le lien le plus précis est actif", () => {
  assert.ok(library && isNavGroup(library));
  assert.equal(activeChildHref(library.children, "/library/coach/"), "/library/coach");
  assert.equal(activeChildHref(library.children, "/library/"), "/library");
  assert.equal(activeChildHref(library.children, "/library/radio"), "/library/radio");
  assert.equal(activeChildHref(library.children, "/schedule/"), null);
});

test("l'interface simplifiée masque aussi les liens avancés d'un groupe", () => {
  const hrefs = (simplified: boolean) => visibleNavEntries(simplified).flatMap((entry) => (isNavGroup(entry) ? entry.children : [entry])).map((link) => link.href);
  assert.ok(hrefs(false).includes("/library/coach"));
  assert.ok(!hrefs(true).includes("/library/coach"));
  assert.ok(hrefs(true).includes("/library/radio"));
});
