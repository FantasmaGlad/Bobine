import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { shareIdenticalAssets } from "../scripts/share-assets.mjs";

function write(root: string, path: string, content: string) {
  const full = join(root, path);
  mkdirSync(join(full, ".."), { recursive: true });
  writeFileSync(full, content);
}

test("les fichiers identiques dans toutes les langues sont mutualisés, les autres restent", () => {
  const root = mkdtempSync(join(tmpdir(), "bobine-share-"));
  for (const lang of ["fr", "en"]) {
    write(root, `${lang}/_next/static/chunks/same.js`, "commun");
    write(root, `${lang}/logo.png`, "png");
    write(root, `${lang}/index.html`, "<html></html>");
    write(root, `${lang}/_next/static/chunks/dict.js`, `dictionnaire ${lang}`);
  }
  write(root, "fr/only-fr.js", "fr");
  const result = shareIdenticalAssets(root, ["fr", "en"]);
  assert.equal(result.files, 2);
  assert.equal(readFileSync(join(root, "_shared/_next/static/chunks/same.js"), "utf8"), "commun");
  assert.ok(!existsSync(join(root, "fr/_next/static/chunks/same.js")) && !existsSync(join(root, "en/_next/static/chunks/same.js")));
  assert.ok(existsSync(join(root, "fr/index.html")) && existsSync(join(root, "en/index.html")));
  assert.equal(readFileSync(join(root, "en/_next/static/chunks/dict.js"), "utf8"), "dictionnaire en");
  assert.ok(existsSync(join(root, "fr/only-fr.js")));
});
