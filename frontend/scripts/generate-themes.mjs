#!/usr/bin/env node
// Écrit src/app/themes.css à partir des palettes de src/lib/themePalettes.ts (source unique) :
//   node scripts/generate-themes.mjs          écrit le fichier
//   node scripts/generate-themes.mjs --check  échoue si le fichier n'est pas à jour (utilisé par un test)
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { SEMANTIC_COLORS, THEMES, deriveTokens, paletteOf } from "../src/lib/themePalettes.ts";

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
  return `/* GÉNÉRÉ par scripts/generate-themes.mjs depuis src/lib/themePalettes.ts : ne pas modifier à la main.\n   Neuf thèmes, chacun en clair et en sombre : les quatre couleurs de la palette et les jetons qui en sont déduits. */\n:root {\n${semantic}\n}\n\n${blocks.join("\n\n")}\n`;
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
