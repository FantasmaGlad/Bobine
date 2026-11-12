import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";

export const SHARED_DIR = "_shared";
const KEEP_PER_LANGUAGE = new Set([".html", ".txt"]);

function listFiles(dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) files.push(...listFiles(path));
    else files.push(path);
  }
  return files;
}

const digest = (path) => createHash("sha256").update(readFileSync(path)).digest("hex");

export function shareIdenticalAssets(root, languages) {
  const [first, ...others] = languages;
  const shared = join(root, SHARED_DIR);
  let files = 0;
  let bytes = 0;
  for (const path of listFiles(join(root, first))) {
    const rel = relative(join(root, first), path);
    if (KEEP_PER_LANGUAGE.has(rel.slice(rel.lastIndexOf(".")))) continue;
    const copies = others.map((language) => join(root, language, rel));
    if (!copies.every((copy) => { try { return statSync(copy).isFile() && digest(copy) === digest(path); } catch { return false; } })) continue;
    const target = join(shared, rel);
    mkdirSync(dirname(target), { recursive: true });
    bytes += statSync(path).size * languages.length;
    renameSync(path, target);
    for (const copy of copies) rmSync(copy);
    files += 1;
  }
  return { files, bytes: bytes - bytes / languages.length };
}
