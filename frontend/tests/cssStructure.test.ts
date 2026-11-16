import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

const SRC = join(import.meta.dirname, "..", "src");
const STYLES = join(SRC, "styles");
const MAX_LINES = 500;
const GENERATED = ["app/themes.css"];
const BREAKPOINTS = new Set([
  "max-width: 640px", "max-width: 720px", "max-width: 768px", "max-width: 820px", "max-width: 860px",
  "max-width: 900px", "max-width: 960px", "max-width: 1120px", "max-width: 1440px",
  "min-width: 700px", "min-width: 769px", "min-width: 821px", "min-width: 900px", "min-width: 901px",
  "max-height: 480px", "max-height: 640px",
]);

function cssFiles(dir: string): string[] {
  return (readdirSync(dir, { recursive: true }) as string[])
    .filter((name) => name.endsWith(".css"))
    .map((name) => relative(SRC, join(dir, name)));
}

const sheets = cssFiles(STYLES).filter((path) => path !== "styles/index.css");
const imports = [...readFileSync(join(STYLES, "index.css"), "utf8").matchAll(/@import "([^"]+)";/g)].map((m) =>
  relative(SRC, join(STYLES, m[1])),
);

test("tout le CSS vit dans styles/, hors fichiers générés", () => {
  assert.deepEqual(cssFiles(SRC).filter((path) => !path.startsWith("styles/") && !GENERATED.includes(path)), []);
});

test("index.css importe chaque feuille exactement une fois", () => {
  assert.deepEqual([...imports].sort(), [...sheets, ...GENERATED].sort());
});

test("aucune feuille ne dépasse la taille limite", () => {
  const oversized = sheets
    .map((path) => ({ path, lines: readFileSync(join(SRC, path), "utf8").split("\n").length }))
    .filter((sheet) => sheet.lines > MAX_LINES)
    .map((sheet) => `${sheet.path} (${sheet.lines})`);
  assert.deepEqual(oversized, []);
});

test("aucune feuille ne contient de commentaire", () => {
  assert.deepEqual(sheets.filter((path) => readFileSync(join(SRC, path), "utf8").includes("/*")), []);
});

test("les points de rupture restent dans la liste commune", () => {
  const unknown = sheets.flatMap((path) =>
    [...readFileSync(join(SRC, path), "utf8").matchAll(/@media[^{]*/g)]
      .flatMap((m) => [...m[0].matchAll(/(?:max|min)-(?:width|height):\s*[\d.]+(?:px|em|rem)/g)])
      .map((m) => m[0].replace(/:\s*/, ": "))
      .filter((query) => !BREAKPOINTS.has(query))
      .map((query) => `${path} : ${query}`),
  );
  assert.deepEqual(unknown, []);
});
