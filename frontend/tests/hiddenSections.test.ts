import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const SRC = join(import.meta.dirname, "..", "src");

function files(dir: string, ext: string): string[] {
  return (readdirSync(dir, { recursive: true }) as string[]).filter((name) => name.endsWith(ext)).map((name) => join(dir, name));
}

function hiddenClasses(): Set<string> {
  const found = new Set<string>();
  for (const file of files(join(SRC, "components"), ".tsx").concat(files(join(SRC, "app"), ".tsx"))) {
    for (const [tag] of readFileSync(file, "utf8").matchAll(/<(?:div|section)\b[^>]*>/g)) {
      if (!/\shidden=/.test(tag)) continue;
      const names = /className="([^"]+)"/.exec(tag)?.[1].split(/\s+/) ?? [];
      names.forEach((name) => found.add(name));
    }
  }
  return found;
}

test("une section masquée par l'attribut hidden ne peut pas être réaffichée par son display", () => {
  const css = files(join(SRC, "styles"), ".css").map((file) => readFileSync(file, "utf8")).join("\n");
  const shown = [...hiddenClasses()].filter((name) => {
    const plain = new RegExp(`(^|[\\s,}])\\.${name}\\s*\\{[^}]*\\bdisplay\\s*:`, "m").test(css);
    const guarded = new RegExp(`\\.${name}\\[hidden\\]\\s*[,{]`).test(css);
    return plain && !guarded;
  });
  assert.deepEqual(shown, []);
});
