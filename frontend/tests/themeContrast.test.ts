import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * Garde-fou des 16 thèmes : les jetons du CSS (pas des copies) sont résolus, mélangés et comparés.
 * Toute nouvelle surface posée sur ces jetons hérite de la vérification ; un thème ajouté est testé d'office.
 */
const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

type Rgba = { r: number; g: number; b: number; a: number };

/** Déclarations `--jeton: valeur;` de chaque règle dont un sélecteur est `:root` ou `:root[data-theme="x"]`, dans l'ordre du fichier. */
function rules(): Array<{ selectors: string[]; vars: Record<string, string> }> {
  const out: Array<{ selectors: string[]; vars: Record<string, string> }> = [];
  for (const m of css.matchAll(/(^|\n)(:root[^{}]*)\{([^{}]*)\}/g)) {
    const selectors = m[2].split(",").map((s) => s.trim());
    const vars: Record<string, string> = {};
    for (const d of m[3].matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) vars[d[1]] = d[2].trim().replace(/\s+/g, " ");
    out.push({ selectors, vars });
  }
  return out;
}
const ALL_RULES = rules();
const THEMES = [...new Set(ALL_RULES.flatMap((r) => r.selectors).map((s) => /data-theme="([\w-]+)"/.exec(s)?.[1]).filter(Boolean))] as string[];

function themeVars(theme: string): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const r of ALL_RULES) {
    if (r.selectors.includes(":root") || r.selectors.includes(`:root[data-theme="${theme}"]`)) Object.assign(vars, r.vars);
  }
  return vars;
}

function splitTopLevel(text: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let cur = "";
  for (const ch of text) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === "," && depth === 0) { parts.push(cur.trim()); cur = ""; } else cur += ch;
  }
  parts.push(cur.trim());
  return parts;
}

/** Évalue #hex, rgb()/rgba(), transparent, black, var(--x) et color-mix(in srgb, A p%, B) (mélange prémultiplié CSS Color 5). */
function evaluate(expr: string, vars: Record<string, string>): Rgba {
  const e = expr.trim();
  if (e === "transparent") return { r: 0, g: 0, b: 0, a: 0 };
  if (e === "black") return { r: 0, g: 0, b: 0, a: 1 };
  if (e === "white") return { r: 255, g: 255, b: 255, a: 1 };
  const hex = /^#([0-9a-f]{6})$/i.exec(e);
  if (hex) return { r: parseInt(hex[1].slice(0, 2), 16), g: parseInt(hex[1].slice(2, 4), 16), b: parseInt(hex[1].slice(4, 6), 16), a: 1 };
  const rgb = /^rgba?\(([^)]+)\)$/.exec(e);
  if (rgb) {
    const [r, g, b, a = "1"] = rgb[1].split(",").map((x) => x.trim());
    return { r: +r, g: +g, b: +b, a: +a };
  }
  const v = /^var\(--([\w-]+)\)$/.exec(e);
  if (v) {
    assert.ok(vars[v[1]] !== undefined, `jeton --${v[1]} introuvable`);
    return evaluate(vars[v[1]], vars);
  }
  const mix = /^color-mix\(([\s\S]*)\)$/.exec(e);
  if (mix) {
    const [space, c1, c2] = splitTopLevel(mix[1]);
    assert.equal(space, "in srgb");
    const pct = (s: string) => {
      const m = /^(.*?)\s+([\d.]+)%$/.exec(s);
      return m ? { color: m[1], p: +m[2] / 100 } : { color: s, p: undefined };
    };
    let { color: ca, p: pa } = pct(c1);
    let { color: cb, p: pb } = pct(c2);
    if (pa === undefined && pb === undefined) pa = pb = 0.5;
    else if (pa === undefined) pa = 1 - (pb as number);
    else if (pb === undefined) pb = 1 - pa;
    const A = evaluate(ca, vars);
    const B = evaluate(cb, vars);
    const wa = (pa as number) * A.a;
    const wb = (pb as number) * B.a;
    const alpha = wa + wb;
    if (alpha === 0) return { r: 0, g: 0, b: 0, a: 0 };
    return { r: (A.r * wa + B.r * wb) / alpha, g: (A.g * wa + B.g * wb) / alpha, b: (A.b * wa + B.b * wb) / alpha, a: alpha };
  }
  throw new Error(`expression non prise en charge : ${e}`);
}

const over = (top: Rgba, below: Rgba): Rgba => {
  const a = top.a + below.a * (1 - top.a);
  const mix = (t: number, b: number) => (t * top.a + b * below.a * (1 - top.a)) / a;
  return { r: mix(top.r, below.r), g: mix(top.g, below.g), b: mix(top.b, below.b), a };
};
const lum = (c: Rgba) => {
  const f = (v: number) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
};
function ratio(a: Rgba, b: Rgba): number {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Couleur de `expr` posée sur le fond de page du thème (les surfaces de verre sont translucides). */
function onPage(expr: string, vars: Record<string, string>): Rgba {
  return over(evaluate(expr, vars), evaluate("var(--bg-main)", vars));
}

const AA = 4.5;
const NON_TEXT = 3;

test("les 16 thèmes sont couverts", () => {
  assert.equal(THEMES.length, 16);
});

for (const theme of THEMES) {
  const vars = themeVars(theme);
  const c = (expr: string) => evaluate(expr, vars);

  test(`${theme} : texte courant lisible sur les surfaces`, () => {
    for (const surface of ["bg-main", "bg-surface", "bg-surface-elevated"]) {
      assert.ok(ratio(c("var(--text-main)"), c(`var(--${surface})`)) >= 7, `text-main sur ${surface}`);
      assert.ok(ratio(c("var(--text-muted)"), c(`var(--${surface})`)) >= AA, `text-muted sur ${surface}`);
      assert.ok(ratio(c("var(--text-dim)"), c(`var(--${surface})`)) >= AA, `text-dim sur ${surface}`);
    }
  });

  test(`${theme} : texte d'erreur lisible sur les surfaces`, () => {
    const tinted = "color-mix(in srgb, var(--accent-error) 15%, var(--bg-surface-elevated))"; // encarts d'erreur teintés
    for (const surface of ["var(--bg-main)", "var(--bg-surface)", "var(--bg-surface-elevated)", tinted]) {
      const got = ratio(c("var(--accent-error-text)"), over(c(surface), c("var(--bg-main)")));
      assert.ok(got >= AA, `accent-error-text sur ${surface} : ${got.toFixed(2)}`);
    }
  });

  test(`${theme} : bouton principal (texte sur son fond réel, posé sur la page)`, () => {
    // Fond effectif : celui que le CSS impose à ce thème (règle des thèmes clairs) sinon `.btn-primary`.
    const themed = new RegExp(`:root\\[data-theme="${theme}"\\] \\.btn-primary:not\\(:disabled\\)[^{]*\\{[^}]*?background-color:\\s*([^;]+);`).exec(css)?.[1];
    const fill = themed ?? /\n\.btn-primary \{[^}]*?background:\s*([^;]+);/.exec(css)?.[1];
    assert.ok(fill && !fill.includes("gradient"), "fond du bouton principal introuvable ou en dégradé translucide");
    assert.ok(ratio(c("var(--accent-primary-fg)"), onPage(fill, vars)) >= AA, `fond ${fill}`);
  });

  test(`${theme} : verre flottant, voile média et code d'association portent du texte AA`, () => {
    const text = c("var(--text-main)");
    for (const glass of ["--glass-floating-bg", "--glass-surface-bg", "--bg-surface-elevated 92%"]) {
      const expr = glass.includes("%") ? "color-mix(in srgb, var(--bg-surface-elevated) 92%, transparent)" : `var(${glass})`;
      assert.ok(ratio(text, onPage(expr, vars)) >= 7, `text-main sur ${glass}`);
    }
  });

  test(`${theme} : anneau de sélection et jauge distincts du fond (3:1)`, () => {
    const accent = c("var(--accent-primary)");
    assert.ok(ratio(accent, c("var(--bg-main)")) >= NON_TEXT, "anneau sur fond de page");
    const trackBg = /\.volume-osd-track \{[^}]*?background:\s*([^;]+);/.exec(css)?.[1];
    assert.ok(trackBg, "piste de la jauge introuvable dans le CSS");
    const track = onPage(trackBg, vars);
    assert.ok(ratio(accent, over(track, onPage("var(--glass-floating-bg)", vars))) >= NON_TEXT, "jauge sur sa piste");
  });
}
