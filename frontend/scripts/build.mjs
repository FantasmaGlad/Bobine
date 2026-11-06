// Construit l'interface une fois par langue : out/fr et out/en. Le backend sert celui de la langue enregistrée
// (backend/app/utils/ui_language.py) ; tous les empaquetages copient `frontend/out` tel quel.
import { spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, renameSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { shareIdenticalAssets } from "./share-assets.mjs";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const staging = join(root, "out-build");
const only = process.argv.slice(2);
const languages = only.length ? only : ["fr", "en"];

// Jamais d'export d'un ancien build à la racine de out/ : le backend le servirait aux deux langues.
rmSync(join(root, "out"), { recursive: true, force: true });
rmSync(staging, { recursive: true, force: true });
mkdirSync(staging, { recursive: true });
for (const language of languages) {
  const run = spawnSync("npx", ["next", "build"], {
    cwd: root,
    stdio: "inherit",
    shell: process.platform === "win32",
    env: { ...process.env, NEXT_PUBLIC_BOBINE_LANG: language },
  });
  if (run.status !== 0) {
    rmSync(staging, { recursive: true, force: true });
    rmSync(join(root, "out"), { recursive: true, force: true });
    process.exit(run.status ?? 1);
  }
  if (!existsSync(join(root, "out", "index.html"))) {
    console.error(`Export ${language} introuvable dans out/`);
    process.exit(1);
  }
  cpSync(join(root, "out"), join(staging, language), { recursive: true });
}
if (languages.length > 1) {
  const shared = shareIdenticalAssets(staging, languages);
  console.log(`Fichiers communs mutualisés : ${shared.files} (${(shared.bytes / 1024).toFixed(0)} Ko économisés par paquet)`);
}
rmSync(join(root, "out"), { recursive: true, force: true });
renameSync(staging, join(root, "out"));
console.log(`Exports construits : ${languages.join(", ")} (out/<langue>, out/_shared)`);
