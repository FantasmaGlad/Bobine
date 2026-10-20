import { test } from "node:test";
import assert from "node:assert/strict";
import { formatAge, formatBytes, installHintKey, isBlockError, problemKeys, reportAsText, type ImportDiagnostics } from "../src/lib/importDiagnostics.ts";
import { dictionaries } from "../src/lib/i18n.ts";

const dir = (path: string, free: number) => ({ path, exists: true, writable: true, free_bytes: free, total_bytes: free * 2 });
const sample: ImportDiagnostics = {
  generated_at: 1_700_000_000,
  os: "macos",
  frozen: true,
  ffmpeg: { path: "ffmpeg", found: false, executable: false, version: null, error: "introuvable" },
  ffprobe: { error: "RuntimeError: panne" },
  temp_dir: dir("/tmp/bobine", 5 * 1024 ** 3),
  staging_dir: { ...dir("/tmp/bobine/bobine-uploads", 1024 ** 3), partial_uploads: 2, partial_bytes: 3 * 1024 ** 2 },
  media_dir: { path: "/m", exists: true, writable: false, free_bytes: 800 * 1024 ** 2, total_bytes: null, error: "écriture impossible" },
  executors: { ffmpeg: { max_workers: 1, threads_started: 1, threads_alive: 1, queued: 3, shutdown: false }, io: { max_workers: 2, threads_started: 0, threads_alive: 0, queued: 0, shutdown: false } },
  jobs: { active: [{ id: "abcd1234", kind: "video", source: "upload", stage: "normalizing", age_seconds: 4000, idle_seconds: 700, queue_position: 0 }], counts: { normalizing: 1 } },
  problems: ["ffmpeg_unavailable", "job_stuck", "code_futur_inconnu"],
};

test("un bloc en échec se distingue d'un bloc valide", () => {
  assert.equal(isBlockError({ error: "boom" }), true);
  assert.equal(isBlockError(sample.ffmpeg), false);
  assert.equal(isBlockError(sample.temp_dir), false);
  assert.equal(isBlockError(sample.ffprobe), true);
});

test("les constats connus sont traduits, un code inconnu est ignoré", () => {
  assert.deepEqual(problemKeys(sample.problems), [
    "settingsPage.importDiag.problems.ffmpeg_unavailable",
    "settingsPage.importDiag.problems.job_stuck",
  ]);
  assert.deepEqual(problemKeys(undefined), []);
});

test("l'aide d'installation suit le système du serveur", () => {
  assert.equal(installHintKey("macos"), "uploads.errors.installHint.macos");
  assert.equal(installHintKey("plan9"), "uploads.errors.installHint.linux");
  assert.equal(installHintKey({ error: "x" }), "uploads.errors.installHint.linux");
});

test("formats d'octets et de durées", () => {
  assert.equal(formatBytes(512 * 1024), "512 Ko");
  assert.equal(formatBytes(5 * 1024 ** 2), "5.0 Mo");
  assert.equal(formatBytes(800 * 1024 ** 2), "800 Mo");
  assert.equal(formatBytes(5 * 1024 ** 3), "5.0 Go");
  assert.equal(formatBytes(null), "—");
  assert.equal(formatAge(45), "45 s");
  assert.equal(formatAge(600), "10 min");
  assert.equal(formatAge(3 * 3600 + 300), "3 h 05");
  assert.equal(formatAge(-1), "—");
});

test("le rapport texte garde chaque bloc lisible même quand l'un d'eux a échoué", () => {
  const text = reportAsText(sample);
  assert.match(text, /Système : macos \(application empaquetée\)/);
  assert.match(text, /ffmpeg : introuvable \[introuvable\]/);
  assert.match(text, /ffprobe : indisponible \(RuntimeError: panne\)/);
  assert.match(text, /Dossier des médias : \/m — NON inscriptible, 800 Mo libres/);
  assert.match(text, /Exécuteur ffmpeg : 1\/1 thread\(s\) actif\(s\), 3 en attente/);
  assert.match(text, /video normalizing \(âge 1 h 06, sans mise à jour depuis 12 min\)/);
  assert.match(text, /Constats : ffmpeg_unavailable, job_stuck/);
});

function lookup(dict: unknown, key: string): unknown {
  return key.split(".").reduce<unknown>((node, part) => (node && typeof node === "object" ? (node as Record<string, unknown>)[part] : undefined), dict);
}

test("les clés settingsPage.importDiag.* existent en français et en anglais", () => {
  const keys = [
    "title", "hint", "refresh", "refreshing", "copy", "copied", "loadError", "allGood",
    "ffmpeg", "ffprobe", "found", "missing", "notExecutable", "tempDir", "stagingDir", "mediaDir",
    "writable", "notWritable", "free", "partialUploads", "executor", "executorValue", "jobs", "noJobs", "jobLine", "blockError",
    "problems.ffmpeg_unavailable", "problems.ffprobe_unavailable", "problems.temp_not_writable",
    "problems.disk_low", "problems.job_stuck", "problems.executor_shutdown",
  ].map((k) => `settingsPage.importDiag.${k}`);
  for (const key of keys) {
    assert.equal(typeof lookup(dictionaries.fr, key), "string", `fr manquant : ${key}`);
    assert.equal(typeof lookup(dictionaries.en, key), "string", `en manquant : ${key}`);
  }
});
