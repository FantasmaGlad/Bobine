import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const MAX_LINES = 500;
const SRC = join(import.meta.dirname, "..", "src");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "i18n" ? [] : sources(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

test("aucun fichier source du frontend ne dépasse la taille limite", () => {
  const oversized = sources(SRC)
    .map((path) => ({ path: relative(SRC, path), lines: readFileSync(path, "utf8").split("\n").length }))
    .filter((file) => file.lines > MAX_LINES)
    .map((file) => `${file.path} (${file.lines})`);
  assert.deepEqual(oversized, []);
});
