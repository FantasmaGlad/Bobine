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

  test(`${theme} : zone d'effacement du formatage (fond teinté par le jeton d'erreur) porte du texte AA`, () => {
    const fill = /\.fmt-erase \{[^}]*?background:\s*([^;]+);/.exec(css)?.[1];
    assert.ok(fill, "fond de .fmt-erase introuvable dans le CSS");
    const surface = over(c(fill), c("var(--bg-main)"));
    assert.ok(ratio(c("var(--text-main)"), surface) >= 7, "text-main sur la zone d'effacement");
    assert.ok(ratio(c("var(--text-muted)"), surface) >= AA, "text-muted sur la zone d'effacement");
    assert.ok(ratio(c("var(--accent-error-text)"), surface) >= AA, "titre d'erreur sur la zone d'effacement");
  });

  test(`${theme} : options et champs du formatage sur leur matériau composé`, () => {
    const floating = onPage("var(--glass-floating-bg)", vars);
    const card = vars["glass-card-bg"];
    const stops = card.startsWith("linear-gradient(")
      ? splitTopLevel(card.slice("linear-gradient(".length, -1)).slice(1).map((v) => v.replace(/\s+\d+%$/, ""))
      : [card];
    const normal = stops.map((stop) => over(c(stop), floating));
    const selected = over(c("color-mix(in srgb, var(--accent-primary) 10%, var(--bg-surface-elevated))"), floating);
    const chip = over(c("var(--glass-surface-bg)"), floating);
    for (const surface of [...normal, selected, chip]) {
      assert.ok(ratio(c("var(--text-main)"), surface) >= 7, "texte principal AAA sur les options");
      assert.ok(ratio(c("var(--text-muted)"), surface) >= AA, "texte secondaire AA sur les options");
      assert.ok(ratio(c("var(--control-outline)"), surface) >= NON_TEXT, "sélection visible sur les options");
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

// --- Routage audio et table de mixage des sorties radio (matériau ajouté avec les phases 2 et 3) ---

/** Valeur de la déclaration `property` de la première règle `selector { … }` du CSS. */
function declaration(selector: string, property: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const block = new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`).exec(css)?.[1];
  assert.ok(block, `${selector} introuvable dans le CSS`);
  const value = new RegExp(`(?:^|[;\\s])${property}\\s*:\\s*([^;]+);?`).exec(block)?.[1];
  assert.ok(value, `${selector} : ${property} introuvable`);
  return value.trim().replace(/\s+/g, " ");
}

test("routage et mixage : les surfaces de tranche et de nœud sont celles dont le texte est déjà vérifié", () => {
  assert.equal(declaration(".rt-node-card", "fill"), "var(--bg-surface-elevated)");
  assert.equal(declaration(".mx-strip", "background"), "var(--bg-surface-elevated)");
  assert.equal(declaration(".rt-node-label", "fill"), "var(--text-main)");
  assert.equal(declaration(".rt-node-sub", "fill"), "var(--text-muted)");
  assert.equal(declaration(".mx-toggle", "color"), "var(--text-main)");
});

for (const theme of THEMES) {
  const vars = themeVars(theme);
  const c = (expr: string) => evaluate(expr, vars);

  test(`${theme} : routage et mixage (bascules, vumètre, arêtes du graphe)`, () => {
    const strip = onPage(declaration(".mx-strip", "background"), vars);
    // Solo actif : texte sur le fond d'accent.
    const solo = ratio(c(declaration(".mx-toggle--solo.is-on", "color")), onPage(declaration(".mx-toggle--solo.is-on", "background"), vars));
    assert.ok(solo >= AA, `solo actif : ${solo.toFixed(2)}`);
    // Sourdine active : texte d'erreur sur son fond teinté.
    const muteBg = over(c(declaration(".mx-toggle--mute.is-on", "background")), strip);
    const mute = ratio(c(declaration(".mx-toggle--mute.is-on", "color")), muteBg);
    assert.ok(mute >= AA, `sourdine active : ${mute.toFixed(2)}`);
    // Vumètre : le remplissage se distingue de sa piste (3:1), y compris la zone de saturation.
    const track = over(c(declaration(".mx-meter", "background")), strip);
    for (const fill of [declaration(".mx-meter-fill", "background"), declaration(".mx-meter-fill.is-hot", "background")]) {
      const got = ratio(c(fill), track);
      assert.ok(got >= NON_TEXT, `vumètre ${fill} sur sa piste : ${got.toFixed(2)}`);
    }
    // Arêtes du graphe sur le fond de la zone de graphe : route (accent), liaison par défaut (texte atténué), sortie absente.
    const frame = onPage(declaration(".rt-graph-frame", "background"), vars);
    for (const [rule, expect] of [[".rt-edge--route", "stroke"], [".rt-edge", "stroke"], [".rt-edge.is-absent", "stroke"]] as const) {
      const got = ratio(c(declaration(rule, expect)), frame);
      assert.ok(got >= NON_TEXT, `${rule} sur le graphe : ${got.toFixed(2)}`);
    }
    // Icônes d'état (en plus du texte) des cartes de routage sur le verre.
    const card = onPage(declaration(".rt-card, .mx-channel", "background"), vars);
    const ok = ratio(c(declaration(".rt-status--ok .material-symbols-outlined", "color")), card);
    const warn = ratio(c(declaration(".rt-status--warn .material-symbols-outlined", "color")), card);
    assert.ok(ok >= NON_TEXT, `icône d'état « appliqué » : ${ok.toFixed(2)}`);
    assert.ok(warn >= NON_TEXT, `icône d'état « attention » : ${warn.toFixed(2)}`);
  });
}

// Chaque combinaison des extrêmes du maillage forme une enveloppe conservative,
// même lorsque les centres des dégradés ne se croisent pas.
const LIGHT_THEMES = new Set(["clair", "charbon", "miel", "menthe", "ciel", "lavande", "beige", "coco"]);
function resolveToken(expr: string, vars: Record<string, string>): string {
  const match = /^var\(--([\w-]+)\)$/.exec(expr);
  return match ? resolveToken(vars[match[1]], vars) : expr;
}
function gradientStops(expr: string, vars: Record<string, string>): string[] {
  const value = resolveToken(expr, vars);
  return /^(linear|radial)-gradient\(/.test(value)
    ? splitTopLevel(value.slice(value.indexOf("(") + 1, -1)).slice(1).map(v => v.replace(/\s+[\d.]+%$/, ""))
    : [value];
}
function contentSurfaces(vars: Record<string, string>): Rgba[] {
  const layers = splitTopLevel(resolveToken(declaration(".page-content", "background-image"), vars));
  let surfaces = [evaluate(declaration(".page-content", "background-color"), vars)];
  for (const layer of layers.reverse()) {
    surfaces = surfaces.flatMap(below => gradientStops(layer, vars).map(stop => over(evaluate(stop, vars), below)));
  }
  return surfaces;
}
// Matrice saturate() de CSS Filter Effects appliquée au fond avant le verre.
function saturateBackdrop(c: Rgba, amount: number): Rgba {
  const y = .213 * c.r + .715 * c.g + .072 * c.b;
  const channel = (v: number) => Math.max(0, Math.min(255, y + amount * (v - y)));
  return { r: channel(c.r), g: channel(c.g), b: channel(c.b), a: c.a };
}
for (const theme of THEMES) {
  const vars = themeVars(theme);
  const c = (expr: string) => evaluate(expr, vars);
  test(`${theme} : contenu et verre sur le maillage composé`, () => {
    assert.equal(declaration(".mobile-page-content", "background-color"), declaration(".page-content", "background-color"));
    const surfaces = contentSurfaces(vars);
    const saturation = parseFloat(vars["saturate-rich"]) / 100;
    const glass = surfaces.flatMap(bg => gradientStops("var(--glass-card-bg)", vars)
      .map(stop => over(c(stop), saturateBackdrop(bg, saturation))));
    // Les thèmes clairs gardent leur matériau historique : égalité vérifiée ci-dessous.
    // Les seuils composés portent ici sur les huit surfaces sombres modifiées.
    // Le mode système sans transparence remplace les cartes par ce fond opaque.
    for (const bg of LIGHT_THEMES.has(theme) ? [] : [...surfaces, ...glass, c("var(--bg-surface-elevated)")]) {
      for (const [token, min] of [["text-main", 7], ["text-muted", AA], ["content-text-dim", AA]] as const) {
        const got = ratio(c(`var(--${token})`), bg);
        assert.ok(got >= min, `${token} : ${got.toFixed(2)} < ${min}`);
      }
    }
    if (LIGHT_THEMES.has(theme)) {
      assert.deepEqual(c("var(--bg-content)"), c("var(--bg-main)"));
      assert.equal(resolveToken("var(--bg-content-mesh)", vars), resolveToken("var(--bg-ambient-mesh)", vars));
      assert.deepEqual(c("var(--content-text-dim)"), c("var(--text-dim)"));
      assert.equal(resolveToken(declaration(".mobile-page-content", "background-image"), vars), "none");
    } else {
      assert.ok(lum(c("var(--bg-content)")) > lum(c("var(--bg-main)")), "contenu plus clair que la coque");
      assert.equal(resolveToken(declaration(".mobile-page-content", "background-image"), vars), resolveToken(declaration(".page-content", "background-image"), vars));
    }
  });
  test(`${theme} : danger, texte et commandes sur les fonds réels`, () => {
    const panel = over(c(declaration(".settings-danger", "background")), c("var(--bg-content)"));
    const card = over(c(declaration(".settings-danger-card", "background")), panel);
    const dangerText = c(declaration(".settings-danger h3", "color"));
    for (const bg of [panel, card]) {
      assert.ok(ratio(c("var(--text-main)"), bg) >= 7, "texte principal");
      assert.ok(ratio(c("var(--text-muted)"), bg) >= AA, `aide et commandes : ${ratio(c("var(--text-muted)"), bg).toFixed(2)}`);
      assert.ok(ratio(dangerText, bg) >= AA, `titres rouges : ${ratio(dangerText, bg).toFixed(2)}`);
    }
    for (const selector of [".settings-danger .btn-danger", ".settings-danger .btn-danger:hover:not(:disabled)", ".settings-danger .btn-danger:active:not(:disabled)"]) {
      const bg = over(c(declaration(selector, "background")), card);
      const fg = c(declaration(".settings-danger .btn-danger", "color"));
      assert.ok(ratio(fg, bg) >= AA, `${selector} : ${ratio(fg, bg).toFixed(2)}`);
      assert.ok(ratio(dangerText, card) >= NON_TEXT, "bordure et focus sur la carte");
    }
  });
}
