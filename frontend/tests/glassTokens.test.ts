import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";

/**
 * Cliquet anti-codage en dur : le verre, les voiles et les ombres passent par les jetons du thème
 * (`--blur-*`, `--saturate-*`, `--glass-*`, `--scrim*`, `--ink`, `--specular`), jamais par des valeurs figées qui ne
 * s'adapteraient ni au thème, ni à « transparence réduite », ni à l'écran. Les plafonds ne peuvent QUE baisser :
 * en migrant des règles, abaissez-les ; ne les relevez jamais, créez ou utilisez un jeton.
 */
const srcDir = new URL("../src/", import.meta.url);
const sourceFiles = (readdirSync(srcDir, { recursive: true }) as string[]).filter((f) => /\.(css|tsx?)$/.test(f));
/** Jetons et règles : tout le CSS (globals, responsive, modules) ; les styles en ligne (.tsx) sont vérifiés à part. */
const css = sourceFiles.filter((f) => f.endsWith(".css")).map((f) => readFileSync(new URL(f, srcDir), "utf8")).join("\n");
const inlineStyles = sourceFiles.filter((f) => /\.tsx?$/.test(f)).map((f) => readFileSync(new URL(f, srcDir), "utf8")).join("\n");

const BASELINE = {
  /** `backdrop-filter` avec un flou en pixels au lieu de `blur(var(--blur-*))`. */
  hardcodedBlur: 0,
  /** `backdrop-filter` dont la valeur n'est qu'un `var()` sans `blur(...)` : invalide, aucun flou n'est appliqué. */
  invalidBlur: 0,
  /** `saturate(NNN%)` figé dans un `backdrop-filter`. */
  hardcodedSaturate: 0,
  /** Blancs figés (`rgba(255,255,255,…)`, `#fff` dans un `color-mix`) au lieu de `var(--specular)`. */
  hardcodedWhite: 0,
  /** Noirs figés (`rgba(0,0,0,…)`, `#000` dans un `color-mix`) au lieu de `var(--ink)` ou d'un voile. */
  hardcodedBlack: 0,
};

/** CSS sans commentaires ni ce qui ne peut légitimement pas porter de variable : URL de données, sous-titres vidéo (`::cue`), définitions des neutres. */
function checkable(): string {
  return css
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/url\([^)]*\)/g, "url()")
    .replace(/::cue\s*\{[^}]*\}/g, "")
    .replace(/^\s*--(ink|specular)\s*:.*$/gm, "");
}
const source = checkable();

/** Valeurs des déclarations `backdrop-filter` (préfixées ou non). */
const filters = (): string[] => [...source.matchAll(/(?<!-webkit-)backdrop-filter\s*:\s*([^;}]+)[;}]/g)].map((m) => m[1].trim());

/** Contenu de chaque `color-mix(...)` (parenthèses équilibrées). */
function colorMixes(): string[] {
  const out: string[] = [];
  for (let i = source.indexOf("color-mix("); i !== -1; i = source.indexOf("color-mix(", i + 1)) {
    let depth = 0;
    for (let j = i + 9; j < source.length; j++) {
      if (source[j] === "(") depth++;
      if (source[j] === ")" && --depth === 0) { out.push(source.slice(i, j + 1)); break; }
    }
  }
  return out;
}

const counts = () => ({
  hardcodedBlur: filters().filter((v) => /blur\(\s*[\d.]+px/.test(v)).length,
  invalidBlur: filters().filter((v) => v !== "none" && !v.includes("blur(")).length,
  hardcodedSaturate: filters().filter((v) => /saturate\(\s*[\d.]+%/.test(v)).length,
  hardcodedWhite: [...source.matchAll(/rgba\(\s*255\s*,\s*255\s*,\s*255/g)].length + colorMixes().filter((c) => /#f{3}\b|#f{6}\b/i.test(c)).length,
  hardcodedBlack: [...source.matchAll(/rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*(?!0\s*\))/g)].length + colorMixes().filter((c) => /#0{3}\b|#0{6}\b/i.test(c)).length,
});

test("verre : flous, saturations, blancs et noirs figés ne dépassent pas le plafond", () => {
  const now = counts();
  if (process.env.GLASS_COUNTS) console.log("COUNTS", JSON.stringify(now));
  for (const key of Object.keys(BASELINE) as Array<keyof typeof BASELINE>) {
    assert.ok(now[key] <= BASELINE[key], `${key} : ${now[key]} (plafond ${BASELINE[key]}) — utiliser un jeton, puis abaisser le plafond`);
  }
});

test("verre : l'échelle de flous et les neutres sont définis", () => {
  for (const token of ["--blur-scale", "--blur-xs", "--blur-sm", "--blur-md", "--blur-lg", "--blur-xl", "--blur-2xl", "--saturate-soft", "--saturate-rich", "--ink", "--specular", "--glass-card-blur"]) {
    assert.ok(new RegExp(`${token}\\s*:`).test(css), `jeton ${token} non défini`);
  }
});

test("composants de verre récents : uniquement des jetons", () => {
  for (const selector of [".volume-osd", ".pairing-code-value"]) {
    const block = new RegExp(`${selector.replace(".", "\\.")} \\{([^}]*)\\}`).exec(css)?.[1];
    assert.ok(block, `${selector} introuvable`);
    assert.ok(!/#[0-9a-f]{3,8}\b/i.test(block), `${selector} : couleur figée`);
    assert.ok(!/rgba?\(/.test(block), `${selector} : rgba figé`);
  }
});

test("jetons : aucune variable utilisée sans être définie", () => {
  // Une variable absente invalide toute la déclaration (ombre, flou…) ou impose un repli figé : bug silencieux.
  const noComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const defined = new Set([...noComments.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
  for (const m of inlineStyles.matchAll(/["'](--[\w-]+)["']/g)) defined.add(m[1]); // `style={{ "--x": … }}`, setProperty
  const undefinedTokens = [...new Set([...noComments.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]))].filter((n) => !defined.has(n));
  assert.deepEqual(undefinedTokens, [], `variables non définies : ${undefinedTokens.join(", ")}`);
});

test("statuts : plus de couleur de statut ni d'accent figés, plus de variable d'accent inexistante", () => {
  assert.ok(!/rgba\(\s*(255\s*,\s*69\s*,\s*58|255\s*,\s*159\s*,\s*10|48\s*,\s*209\s*,\s*88)/.test(source), "statut figé : utiliser --accent-error/-warning/-success");
  assert.ok(!/accent-primary-rgb|--accent-danger/.test(source), "variable d'accent jamais définie");
});

test("transparence réduite : les jetons de verre deviennent opaques et le flou nul", () => {
  const block = /@media \(prefers-reduced-transparency: reduce\)\s*\{([\s\S]*?)\n\}/.exec(css)?.[1];
  assert.ok(block, "bloc prefers-reduced-transparency introuvable");
  for (const token of ["--blur-scale: 0", "--glass-surface-bg", "--glass-card-bg", "--glass-floating-bg"]) {
    assert.ok(block.includes(token), `${token} absent du mode transparence réduite`);
  }
});

test("verre : `-webkit-backdrop-filter` précède toujours `backdrop-filter`", () => {
  // Le minifieur CSS de la chaîne de build ne garde que la dernière des deux déclarations identiques : écrite après,
  // la version préfixée supprime la version standard, et Chrome, Edge et Firefox n'appliquent alors AUCUN flou.
  const wrongOrder = [...source.matchAll(/(?<![-\w])backdrop-filter\s*:[^;{}]+;\s*-webkit-backdrop-filter\s*:/g)].length;
  assert.equal(wrongOrder, 0, `${wrongOrder} règles déclarent backdrop-filter avant -webkit-backdrop-filter`);
});

test("styles en ligne : ni blanc ni noir figé, ni flou en pixels", () => {
  const inline = inlineStyles.replace(/\/\*[\s\S]*?\*\//g, "");
  assert.equal([...inline.matchAll(/rgba\(\s*(?:0\s*,\s*0\s*,\s*0|255\s*,\s*255\s*,\s*255)\s*,/g)].length, 0, "rgba figé dans un style en ligne : color-mix sur var(--ink) ou var(--specular)");
  assert.equal([...inline.matchAll(/backdropFilter\s*:\s*["'`][^"'`]*blur\(\s*[\d.]+px/g)].length, 0, "flou en pixels dans un style en ligne : blur(var(--blur-*))");
});
