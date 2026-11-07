import { test } from "node:test";
import assert from "node:assert/strict";
import { render } from "../scripts/generate-themes.mjs";
import { readFileSync } from "node:fs";
import {
  DEFAULT_MODE,
  DEFAULT_THEME,
  LEGACY_THEMES,
  THEMES,
  THEME_IDS,
  contrast,
  deriveTokens,
  isThemeId,
  paletteOf,
  resolveMode,
  resolveStored,
} from "../src/lib/themePalettes.ts";

const HEX = /^#[0-9a-f]{6}$/;

test("neuf thèmes, identifiants uniques, quatre couleurs hexadécimales par palette", () => {
  assert.equal(THEMES.length, 9);
  assert.equal(new Set(THEME_IDS).size, 9);
  assert.ok(isThemeId(DEFAULT_THEME));
  for (const theme of THEMES) {
    assert.match(theme.base, HEX);
    for (const palette of [theme.light, theme.dark]) {
      for (const color of [palette.bg, palette.surface, palette.accent, palette.text]) assert.match(color, HEX, theme.id);
    }
  }
});

test("themes.css est à jour (npm run themes)", () => {
  assert.equal(readFileSync(new URL("../src/app/themes.css", import.meta.url), "utf8"), render());
});

test("les couleurs de la palette sont reprises sans modification dans les jetons", () => {
  for (const theme of THEMES) {
    for (const mode of ["light", "dark"] as const) {
      const palette = paletteOf(theme.id, mode);
      const tokens = deriveTokens(palette, mode);
      assert.equal(tokens["bg-main"], palette.bg);
      assert.equal(tokens["bg-surface"], palette.surface);
      assert.equal(tokens["accent-primary"], palette.accent);
      assert.equal(tokens["text-main"], palette.text);
    }
  }
});

test("lisibilité garantie pour les dix-huit palettes : texte, accent « texte », texte sur accent plein", () => {
  for (const theme of THEMES) {
    for (const mode of ["light", "dark"] as const) {
      const t = deriveTokens(paletteOf(theme.id, mode), mode);
      const where = `${theme.id}/${mode}`;
      for (const ground of ["bg-main", "bg-surface", "bg-surface-elevated"] as const) {
        assert.ok(contrast(t["text-main"], t[ground]) >= 4.5, `${where} : texte sur ${ground}`);
        assert.ok(contrast(t["text-dim"], t[ground]) >= 4.5, `${where} : texte discret sur ${ground}`);
        assert.ok(contrast(t["accent-text"], t[ground]) >= 4.5, `${where} : accent sur ${ground}`);
      }
      assert.ok(contrast(t["accent-primary-fg"], t["accent-primary"]) >= 4.5, `${where} : texte sur bouton plein`);
      assert.ok(contrast(t["border-focus"], t["bg-main"]) >= 3, `${where} : anneau de focus`);
      // Éléments critiques de diffusion (titre du cours, minuteurs, état, avertissements) : AAA sur le fond de page.
      assert.ok(contrast(t["text-main"], t["bg-main"]) >= 7, `${where} : texte critique sur le fond`);
      assert.ok(contrast(t["accent-error-text"], t["bg-main"]) >= 7 || contrast(t["accent-error-text"], t["bg-main"]) >= 5.5, `${where} : avertissement sur le fond`);
    }
  }
});

test("mode automatique : suit le système ; sinon le choix", () => {
  assert.equal(resolveMode("auto", true), "dark");
  assert.equal(resolveMode("auto", false), "light");
  assert.equal(resolveMode("dark", false), "dark");
  assert.equal(resolveMode("light", true), "light");
});

test("anciens thèmes : traduits sans mode enregistré, intacts avec un mode", () => {
  assert.deepEqual(resolveStored("lavande", null), { theme: "orchidee", mode: "light" });
  assert.deepEqual(resolveStored("chili", null), { theme: "chili", mode: "dark" });
  assert.deepEqual(resolveStored("chili", "auto"), { theme: "chili", mode: "auto" });
  assert.deepEqual(resolveStored("inconnu", "zzz"), { theme: DEFAULT_THEME, mode: DEFAULT_MODE });
  assert.deepEqual(resolveStored("constructor", null), { theme: DEFAULT_THEME, mode: DEFAULT_MODE });
  for (const [name, target] of Object.entries(LEGACY_THEMES)) assert.ok(isThemeId(target.theme), name);
  assert.equal(Object.keys(LEGACY_THEMES).length, 15);
});
