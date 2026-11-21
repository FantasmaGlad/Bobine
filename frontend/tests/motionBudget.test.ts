import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { entryDelayMs, MAX_ENTRY_DELAY_MS } from "../src/lib/entryDelay.ts";

const SRC = join(import.meta.dirname, "..", "src");
const STYLES = join(SRC, "styles");
const COMPOSITED = new Set(["transform", "opacity"]);
const MAX_ENTRY_MS = 200;
const MAX_DELAY_MS = 80;

const css = (readdirSync(STYLES, { recursive: true }) as string[])
  .filter((name) => name.endsWith(".css"))
  .map((name) => readFileSync(join(STYLES, name), "utf8").replace(/\/\*[\s\S]*?\*\//g, ""))
  .join("\n");

function keyframes(): Map<string, Set<string>> {
  const found = new Map<string, Set<string>>();
  for (const match of css.matchAll(/@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}/g)) {
    const properties = found.get(match[1]) ?? new Set<string>();
    for (const declaration of match[2].matchAll(/([\w-]+)\s*:/g)) properties.add(declaration[1]);
    found.set(match[1], properties);
  }
  return found;
}

function animations(): { rule: string; name: string; value: string }[] {
  const names = keyframes();
  const found: { rule: string; name: string; value: string }[] = [];
  for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    for (const declaration of match[2].matchAll(/(?:^|;)\s*animation\s*:\s*([^;]+)/g)) {
      const value = declaration[1].trim();
      const name = value.split(/[\s,]+/).find((token) => names.has(token));
      if (name) found.push({ rule: match[1].trim(), name, value });
    }
  }
  return found;
}

const milliseconds = (token: string) => (token.endsWith("ms") ? Number(token.slice(0, -2)) : Number(token.slice(0, -1)) * 1000);

test("une animation permanente n'anime que transform et opacity", () => {
  const names = keyframes();
  const offending = animations()
    .filter((a) => /\binfinite\b/.test(a.value))
    .filter((a) => [...names.get(a.name)!].some((property) => !COMPOSITED.has(property)))
    .map((a) => `${a.rule} → ${a.name} (${[...names.get(a.name)!].join(", ")})`);
  assert.deepEqual(offending, []);
});

test("une entrée animée dure au plus 200 ms et ne commence pas après 80 ms", () => {
  const slow = animations()
    .filter((a) => !/\binfinite\b/.test(a.value) && !a.value.includes("var("))
    .filter((a) => {
      const [duration = 0, delay = 0] = (a.value.match(/\b\d*\.?\d+m?s\b/g) ?? []).map(milliseconds);
      return duration > MAX_ENTRY_MS || delay > MAX_DELAY_MS;
    })
    .map((a) => `${a.rule} → ${a.value}`);
  const delays = [...css.matchAll(/animation-delay\s*:\s*([^;]+)/g)].map((m) => milliseconds(m[1].trim())).filter((ms) => ms > MAX_DELAY_MS);
  assert.deepEqual(slow, []);
  assert.deepEqual(delays, []);
});

test("un délai d'entrée calculé dans un composant passe par entryDelayMs, plafonné à 80 ms", () => {
  const inline = (readdirSync(SRC, { recursive: true }) as string[])
    .filter((name) => name.endsWith(".tsx"))
    .flatMap((name) => [...readFileSync(join(SRC, name), "utf8").matchAll(/animationDelay\s*:\s*([^,}]+)/g)].map((m) => ({ name, value: m[1].trim() })))
    .filter((use) => !use.value.includes("entryDelayMs("))
    .map((use) => `${use.name} → ${use.value}`);
  assert.deepEqual(inline, []);
  assert.equal(MAX_ENTRY_DELAY_MS, MAX_DELAY_MS);
  assert.deepEqual([0, 1, 4, 800].map(entryDelayMs), [0, 20, 80, 80]);
});
