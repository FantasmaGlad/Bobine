#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { DEFAULT_THEME, SEMANTIC_COLORS, THEMES, deriveTokens, paletteOf } from "../src/lib/themePalettes.ts";

const target = fileURLToPath(new URL("../src/app/themes.css", import.meta.url));

export function render() {
  const blocks = [];
  for (const theme of THEMES) {
    for (const mode of ["light", "dark"]) {
      const tokens = deriveTokens(paletteOf(theme.id, mode), mode);
      const body = Object.entries(tokens).map(([name, value]) => `  --${name}: ${value};`).join("\n");
      blocks.push(`:root[data-theme="${theme.id}"][data-mode="${mode}"] {\n  color-scheme: ${mode};\n${body}\n}`);
    }
  }
  const semantic = Object.entries(SEMANTIC_COLORS).map(([name, value]) => `  --accent-${name}: ${value};`).join("\n");
  const fallback = Object.entries(deriveTokens(paletteOf(DEFAULT_THEME, "dark"), "dark")).map(([name, value]) => `  --${name}: ${value};`).join("\n");
  return `/* Généré par scripts/generate-themes.mjs. */\n:root {\n${fallback}\n${semantic}\n}\n\n${blocks.join("\n\n")}\n`;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const css = render();
  if (process.argv.includes("--check")) {
    if (readFileSync(target, "utf8") !== css) {
      console.error("src/app/themes.css n'est pas à jour : lancer « npm run themes ».");
      process.exit(1);
    }
  } else {
    writeFileSync(target, css);
    console.log(`themes.css : ${THEMES.length * 2} palettes écrites.`);
  }
}
