import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  adviceQuery, breadcrumbs, diffVolumes, formatBytes, fsLabel, isFinished, isSelectable, jobPercent, joinPath, longevitySummary,
  overallTone, primaryAction, selectableEntries, selectionBytes, statusIcon, suggestKind, toggleSelection, visibleNotes, volumeIcon, volumeStatus,
  type BrowseEntry, type LongevityItem, type StorageVolume,
} from "../src/lib/storageApi.ts";
import { isPlugEvent } from "../src/lib/useStorageEvents.ts";
import { dictionaries } from "../src/lib/i18n.ts";

function volume(extra: Partial<StorageVolume> = {}): StorageVolume {
  return {
    key: "u-1", name: "CLUB", label: "CLUB", fstype: "exfat", size_bytes: 64e9, kind: "usb", transport: "usb", rotational: false, mounted: true,
    mounted_read_only: true, connected: true, state: "mounted", uuid_known: true, usage: null,
    assessment: { fstype: "exfat", verdict: "acceptable", reason: "works", notes: [], journal: false, permissions: false, max_file_gib: null, write_allowed: true },
    can_register: true, register_block: null, library: null, health: null, longevity: [], standby: null, ...extra,
  };
}
const entry = (extra: Partial<BrowseEntry>): BrowseEntry => ({ name: "a", path: "a", type: "file", size: 10, mtime: null, media: null, hidden: false, ...extra });

test("tailles lisibles en unités décimales, françaises ou anglaises", () => {
  assert.equal(formatBytes(64e9), "64 Go");
  assert.equal(formatBytes(1.9e12), "1,9 To");
  assert.equal(formatBytes(1.9e12, "en"), "1.9 TB");
  assert.equal(formatBytes(640e6), "640 Mo");
  assert.equal(formatBytes(512), "512 o");
  assert.equal(formatBytes(0), "0 o");
  assert.equal(formatBytes(null), "—");
  assert.equal(formatBytes(-1), "—");
});

test("l'état affiché tient en un mot et ne montre jamais « monté »", () => {
  assert.equal(volumeStatus(volume()), "ready");
  assert.equal(volumeStatus(volume({ mounted: false, state: "present" })), "ready");
  assert.equal(volumeStatus(volume({ state: "busy" })), "busy");
  assert.equal(volumeStatus(volume({ state: "ejecting" })), "ejecting");
  assert.equal(volumeStatus(volume({ connected: false, state: "offline" })), "offline");
  assert.equal(volumeStatus(volume({ health: { available: true, status: "warning", warnings: ["wear_high"] } })), "attention");
  assert.equal(volumeStatus(volume({ library: { registered: true, bytes_written: 1, wear_level: "critical", settings: {} as never } })), "attention");
  for (const id of ["ready", "busy", "ejecting", "offline", "attention"] as const) assert.ok(statusIcon(id)); // état aussi lisible par l'icône que par la couleur
});

test("une seule action principale : explorer, sauf débranché ou en retrait", () => {
  assert.equal(primaryAction(volume()), "explore");
  assert.equal(primaryAction(volume({ state: "busy" })), "explore");
  assert.equal(primaryAction(volume({ connected: false, state: "offline" })), null);
  assert.equal(primaryAction(volume({ state: "ejecting" })), null);
});

test("pire état entre santé lue et usure comptée", () => {
  assert.equal(overallTone({ health: null, library: null }), "unknown");
  assert.equal(overallTone({ health: { available: true, status: "ok", warnings: [] }, library: null }), "ok");
  assert.equal(overallTone({ health: { available: false, status: "unknown", warnings: [] }, library: { registered: true, bytes_written: 0, wear_level: "warning", settings: {} as never } }), "warning");
  assert.equal(overallTone({ health: { available: true, status: "warning", warnings: [] }, library: { registered: true, bytes_written: 0, wear_level: "critical", settings: {} as never } }), "critical");
});

test("fil d'Ariane et chemins relatifs", () => {
  assert.deepEqual(breadcrumbs(""), [{ label: null, path: "" }]);
  assert.deepEqual(breadcrumbs("Cours/RPM"), [{ label: null, path: "" }, { label: "Cours", path: "Cours" }, { label: "RPM", path: "Cours/RPM" }]);
  assert.equal(joinPath("", "a"), "a");
  assert.equal(joinPath("Cours", "a.mp4"), "Cours/a.mp4");
});

test("sélection : dossiers et médias seulement, nature proposée selon le contenu", () => {
  assert.equal(isSelectable(entry({ type: "dir" })), true);
  assert.equal(isSelectable(entry({ media: "video" })), true);
  assert.equal(isSelectable(entry({ media: "subtitle" })), false);
  assert.equal(isSelectable(entry({ media: null })), false);
  const list = [entry({ path: "d", type: "dir" }), entry({ path: "v", media: "video" }), entry({ path: "t" })];
  assert.deepEqual(selectableEntries(list).map((e) => e.path), ["d", "v"]);
  assert.deepEqual(toggleSelection(["a"], "b"), ["a", "b"]);
  assert.deepEqual(toggleSelection(["a", "b"], "a"), ["b"]);
  assert.equal(suggestKind([entry({ media: "video" })]), "video");
  assert.equal(suggestKind([entry({ media: "audio" }), entry({ media: "audio" })]), "radio");
  assert.equal(suggestKind([entry({ type: "dir" })]), "video");
  assert.equal(suggestKind([]), "video");
  assert.equal(selectionBytes([entry({ size: 5 }), entry({ size: null }), entry({ size: 7 })]), 12);
});

test("résumé de protection : recommandé tant que rien n'est désactivé", () => {
  const item = (id: LongevityItem["id"], status: LongevityItem["status"]): LongevityItem => ({ id, status, enabled: status !== "disabled", reason: null });
  assert.deepEqual(longevitySummary([item("read_only", "applied"), item("trim", "unavailable"), item("smart", "unavailable")]), { applied: 1, unavailable: 2, disabled: 0, recommended: true });
  assert.equal(longevitySummary([item("read_only", "disabled")]).recommended, false);
  assert.equal(longevitySummary([]).recommended, true);
});

test("branchements et retraits détectés entre deux relectures", () => {
  const a = volume({ key: "a", name: "A" });
  const b = volume({ key: "b", name: "B" });
  assert.deepEqual(diffVolumes([a], [a, b]), { added: ["B"], removed: [] });
  assert.deepEqual(diffVolumes([a, b], [a], new Set(["b"])), { added: [], removed: [{ name: "B", abrupt: true }] });
  assert.deepEqual(diffVolumes([a], [volume({ key: "a", connected: false, state: "offline" })]), { added: [], removed: [{ name: "A", abrupt: false }] });
});

test("évènements WebSocket : seuls branchement et retrait préviennent partout", () => {
  assert.equal(isPlugEvent({ scope: "volumes", changes: ["added"] }), true);
  assert.equal(isPlugEvent({ scope: "volumes", changes: ["removed_abruptly"] }), true);
  assert.equal(isPlugEvent({ scope: "volumes", changes: ["mounted"] }), false);
  assert.equal(isPlugEvent({ scope: "jobs", changes: [] }), false);
});

test("avancement d'un travail", () => {
  assert.equal(isFinished({ stage: "done" }), true);
  assert.equal(isFinished({ stage: "copying" }), false);
  assert.equal(jobPercent({ progress_percent: 41.6, bytes_done: 1, bytes_total: 2 }), 42);
  assert.equal(jobPercent({ progress_percent: null, bytes_done: 50, bytes_total: 200 }), 25);
  assert.equal(jobPercent({ progress_percent: null, bytes_done: null, bytes_total: null }), null);
  assert.equal(jobPercent({ progress_percent: 250, bytes_done: null, bytes_total: null }), 100);
});

test("requête du conseiller de format", () => {
  assert.equal(adviceQuery("linux", ["windows", "macos", "linux"], "flash", false), "?host=linux&media=flash&others=windows%2Cmacos");
  assert.equal(adviceQuery("windows", [], "hdd", true), "?host=windows&media=hdd&legacy=true");
});

test("libellés et icônes", () => {
  assert.equal(fsLabel("exfat"), "exFAT");
  assert.equal(fsLabel("vfat"), "FAT32");
  assert.equal(fsLabel("ntfs3"), "NTFS");
  assert.equal(fsLabel("ext4"), "ext4");
  assert.equal(fsLabel(null), "—");
  assert.equal(volumeIcon("sd"), "sd_card");
  assert.equal(volumeIcon("other"), "storage");
});

// --- textes : FR et EN couvrent les mêmes clés, aucune clé utilisée ne manque, aucune répétition évidente ---

type Dict = { [key: string]: string | string[] | Dict };
function flatten(dict: Dict, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(dict)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") out[key] = v;
    else if (!Array.isArray(v)) Object.assign(out, flatten(v, key));
  }
  return out;
}
const fr = flatten(dictionaries.fr.storage as Dict, "storage");
const en = flatten(dictionaries.en.storage as Dict, "storage");

test("textes du stockage externe : mêmes clés en français et en anglais", () => {
  assert.deepEqual(Object.keys(en).sort(), Object.keys(fr).sort());
  for (const [key, text] of Object.entries({ ...fr, ...en })) assert.ok(text.trim().length > 0, `${key} vide`);
});

test("textes du stockage externe : variables identiques dans les deux langues", () => {
  const vars = (s: string) => [...s.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).sort().join(",");
  for (const key of Object.keys(fr)) assert.equal(vars(en[key]), vars(fr[key]), `${key} : variables différentes`);
});

test("toutes les clés storage.* écrites dans le code existent", () => {
  const dirs = ["../src/components/storage", "../src/app/storage"];
  const files: string[] = [];
  for (const dir of dirs) {
    for (const f of readdirSync(new URL(dir + "/", import.meta.url))) if (/\.tsx?$/.test(f)) files.push(fileURLToPath(new URL(`${dir}/${f}`, import.meta.url)));
  }
  files.push(fileURLToPath(new URL("../src/components/ClientLayout.tsx", import.meta.url)));
  const known = new Set(Object.keys(fr));
  const prefixes = new Set(Object.keys(fr).map((k) => k.split(".").slice(0, -1).join(".")));
  const missing: string[] = [];
  for (const file of files) {
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(/\bt\(\s*["'`](storage\.[\w.]+)["'`]/g)) if (!known.has(m[1])) missing.push(`${file}: ${m[1]}`);
    // clés dynamiques `storage.xxx.${...}` : le dossier doit exister
    for (const m of src.matchAll(/["'`](storage\.[\w.]+)\.\$\{/g)) if (!prefixes.has(m[1])) missing.push(`${file}: ${m[1]}.*`);
  }
  assert.deepEqual(missing, []);
});

test("aucune répétition : un texte du stockage n'est jamais identique à un autre", () => {
  // Interdit seulement les doublons de PHRASES (≥ 3 mots) ; les mots seuls (« Fermer », « Retour ») sont partagés à dessein.
  const seen = new Map<string, string>();
  const duplicates: string[] = [];
  for (const [key, text] of Object.entries(fr)) {
    if (text.split(/\s+/).length < 3) continue;
    const other = seen.get(text);
    if (other) duplicates.push(`${other} = ${key}`);
    seen.set(text, key);
  }
  assert.deepEqual(duplicates, []);
});

test("le titre d'une page ne répète pas le libellé de navigation", () => {
  const nav = dictionaries.fr.nav as Dict;
  assert.equal(nav.storage, "Stockage externe");
  for (const [key, text] of Object.entries(fr)) assert.notEqual(text, nav.storage, `${key} répète le libellé de navigation`);
});

test("conséquences affichées : jamais une phrase déjà dite par la raison", () => {
  assert.deepEqual(visibleNotes({ reason: "exfat_no_journal", notes: ["no_journal_unplug_risk", "no_unix_permissions", "no_file_limit", "flash_write_wear", "prefer_read_only"] }), ["no_unix_permissions", "no_file_limit", "flash_write_wear"]);
  assert.deepEqual(visibleNotes({ reason: "fat_limits", notes: ["no_journal_unplug_risk", "file_limit_4gib"] }), ["no_journal_unplug_risk"]);
  assert.deepEqual(visibleNotes({ reason: "works", notes: ["a", "b", "c", "d"] }), ["a", "b", "c"]);
});
