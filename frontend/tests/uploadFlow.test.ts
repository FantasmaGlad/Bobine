import { test } from "node:test";
import assert from "node:assert/strict";
import {
  JOB_MISS_LIMIT, POLL_FAILURE_LIMIT, backoffMs, formatNotice, isJobLost, isServerSilent, jobErrorNotice,
  nextMissCount, nextPollFailures, phaseLabelKey, retryNotice,
} from "../src/lib/uploadFlow.ts";
import { dictionaries, translate } from "../src/lib/i18n.ts";

test("une tâche absente n'est perdue qu'après plusieurs sondages consécutifs", () => {
  let misses = 0;
  for (let i = 1; i < JOB_MISS_LIMIT; i++) {
    misses = nextMissCount(misses, false);
    assert.equal(isJobLost(misses), false, `sondage ${i} : pas encore perdue`);
  }
  misses = nextMissCount(misses, false);
  assert.equal(isJobLost(misses), true);
});

test("revoir la tâche remet le compteur d'absences à zéro", () => {
  let misses = nextMissCount(undefined, false);
  misses = nextMissCount(misses, false);
  assert.equal(misses, 2);
  misses = nextMissCount(misses, true);
  assert.equal(misses, 0);
  assert.equal(isJobLost(nextMissCount(misses, false)), false);
});

test("sondages en échec : le serveur est déclaré silencieux à partir du seuil, puis tout se rétablit", () => {
  let failures = 0;
  for (let i = 1; i < POLL_FAILURE_LIMIT; i++) {
    failures = nextPollFailures(failures, false);
    assert.equal(isServerSilent(failures), false);
  }
  failures = nextPollFailures(failures, false);
  assert.equal(isServerSilent(failures), true);
  assert.equal(isServerSilent(nextPollFailures(failures, true)), false);
});

test("l'attente avant reprise double jusqu'à 15 s", () => {
  assert.deepEqual([1, 2, 3, 4, 5, 6, 7].map(backoffMs), [1000, 2000, 4000, 8000, 15000, 15000, 15000]);
  assert.equal(backoffMs(0), 1000);
});

test("le message de reprise donne la tentative en cours sur le maximum", () => {
  assert.deepEqual(retryNotice(3, 8, "uploads.reason.stalled"), { key: "uploads.retrying", params: { attempt: 3, max: 8 } });
  assert.deepEqual(retryNotice(2, 8, "uploads.reason.server", 503), { key: "uploads.retryingServerError", params: { attempt: 2, max: 8, status: 503 } });
});

test("formatNotice traduit la raison avant de l'injecter dans le message", () => {
  const t = (key: string, params?: Record<string, string | number>) =>
    key === "uploads.reason.network" ? "réseau" : `${key}|${params?.reason ?? ""}|${params?.max ?? ""}`;
  const text = formatNotice(t, { key: "uploads.errors.interrupted", params: { max: 8, reasonKey: "uploads.reason.network" } });
  assert.equal(text, "uploads.errors.interrupted|réseau|8");
});

test("libellé de phase : une clé par phase", () => {
  assert.equal(phaseLabelKey("connecting"), "uploads.phase.connecting");
  assert.equal(phaseLabelKey("sending"), "uploads.phase.sending");
  assert.equal(phaseLabelKey("processing"), "uploads.phase.processing");
});

test("erreur de tâche : ffmpeg introuvable devient un message traduisible avec l'aide d'installation du bon système", () => {
  const notice = jobErrorNotice("media_tool_missing", { tool: "ffprobe", os: "macos" });
  assert.deepEqual(notice, { key: "uploads.errors.mediaToolMissing", params: { tool: "ffprobe", hintKey: "uploads.errors.installHint.macos" } });
  const fr = formatNotice((k, p) => translate("fr", k, p), notice!);
  assert.match(fr, /^ffprobe est introuvable/);
  assert.match(fr, /brew install ffmpeg/);
  const en = formatNotice((k, p) => translate("en", k, p), notice!);
  assert.match(en, /^ffprobe was not found/);
  assert.match(en, /Homebrew/);
});

test("erreur de tâche : système inconnu → aide Linux ; code inconnu → texte du serveur conservé", () => {
  assert.equal((jobErrorNotice("media_tool_missing", { tool: "ffmpeg", os: "plan9" })!.params as Record<string, string>).hintKey, "uploads.errors.installHint.linux");
  assert.equal(jobErrorNotice("autre_code", {}), undefined);
  assert.equal(jobErrorNotice(null, null), undefined);
});

// Toute clé émise par la logique d'import doit exister en français ET en anglais.
function lookup(dict: unknown, key: string): unknown {
  return key.split(".").reduce<unknown>((node, part) => (node && typeof node === "object" ? (node as Record<string, unknown>)[part] : undefined), dict);
}

test("les clés uploads.* existent en français et en anglais", () => {
  const keys = [
    "uploads.phase.connecting", "uploads.phase.sending", "uploads.phase.processing",
    "uploads.retrying", "uploads.retryingServerError", "uploads.serverUnreachable",
    "uploads.reason.network", "uploads.reason.timeout", "uploads.reason.stalled", "uploads.reason.server",
    "uploads.errors.sessionTimeout", "uploads.errors.unreachable", "uploads.errors.sessionLost",
    "uploads.errors.interrupted", "uploads.errors.jobLost",
    "uploads.errors.mediaToolMissing", "uploads.errors.installHint.macos", "uploads.errors.installHint.windows",
    "uploads.errors.installHint.linux", "uploads.errors.installHint.android",
  ];
  for (const key of keys) {
    assert.equal(typeof lookup(dictionaries.fr, key), "string", `fr manquant : ${key}`);
    assert.equal(typeof lookup(dictionaries.en, key), "string", `en manquant : ${key}`);
  }
});
