import { test } from "node:test";
import assert from "node:assert/strict";
import {
  canConfirmFormat, canLeaveWizard, defaultFormat, formatFinished, formatTravels, labelProblem, needsNewPlan, primaryAction, reflectionLeft, refusalKey,
  stepIcon, volumeStatus, FORMAT_STEP_ORDER, type FormatOption, type FormatPlan,
} from "../src/lib/storageApi.ts";
import { dictionaries } from "../src/lib/i18n.ts";

const option = (fs: FormatOption["fs"], available = true): FormatOption => ({
  fs, available, unavailable: available ? null : "tool_missing", install_package: null, verdict: "acceptable", reason: "works", notes: [], max_file_gib: null,
  label_max: 11, label: "BOBINE", recommended: false, cluster_bytes: null,
});
const plan = (recommended: FormatOption["fs"], options: FormatOption[]): Pick<FormatPlan, "recommended" | "options"> => ({ recommended, options });

test("format présélectionné : celui du conseiller, sinon le premier disponible, sinon aucun", () => {
  assert.equal(defaultFormat(plan("exfat", [option("ext4"), option("exfat"), option("vfat")])), "exfat");
  assert.equal(defaultFormat(plan("ntfs", [option("ext4"), option("exfat"), option("ntfs", false)])), "ext4");
  assert.equal(defaultFormat(plan("ext4", [option("ext4", false)])), null);
});

test("étiquette : limites propres à chaque format", () => {
  assert.equal(labelProblem("exfat", "Salle 1"), null);
  assert.equal(labelProblem("exfat", "  "), "empty");
  assert.equal(labelProblem("exfat", "x".repeat(12)), "too_long");
  assert.equal(labelProblem("vfat", "x".repeat(12)), "too_long");
  assert.equal(labelProblem("ext4", "é".repeat(9)), "too_long");
  assert.equal(labelProblem("ext4", "é".repeat(8)), null);
  assert.equal(labelProblem("ntfs", "x".repeat(32)), null);
  assert.equal(labelProblem("exfat", "a/b"), "chars");
  assert.equal(labelProblem("vfat", "a.b"), "chars");
  assert.equal(labelProblem("vfat", "é"), "chars");
});

test("confirmation forte : nom exact, case cochée, délai écoulé, PIN si exigé ; jamais un simple clic", () => {
  const base = { typed: "CLUB", expected: "CLUB", acknowledged: true, secondsLeft: 0, pinRequired: false, pin: "", labelOk: true };
  assert.equal(canConfirmFormat(base), true);
  assert.equal(canConfirmFormat({ ...base, typed: " club " }), true);              // insensible à la casse et aux espaces autour
  assert.equal(canConfirmFormat({ ...base, typed: "" }), false);
  assert.equal(canConfirmFormat({ ...base, typed: "CLU" }), false);
  assert.equal(canConfirmFormat({ ...base, acknowledged: false }), false);
  assert.equal(canConfirmFormat({ ...base, secondsLeft: 1 }), false);
  assert.equal(canConfirmFormat({ ...base, labelOk: false }), false);
  assert.equal(canConfirmFormat({ ...base, pinRequired: true, pin: "" }), false);
  assert.equal(canConfirmFormat({ ...base, pinRequired: true, pin: "12345" }), false);
  assert.equal(canConfirmFormat({ ...base, pinRequired: true, pin: "123456" }), true);
  assert.equal(canConfirmFormat({ typed: "", expected: "", acknowledged: true, secondsLeft: 0, pinRequired: false, pin: "", labelOk: true }), false);
});

test("délai de réflexion : décompte en secondes entières, jamais négatif", () => {
  assert.equal(reflectionLeft(1000, 1000, 5), 5);
  assert.equal(reflectionLeft(1000, 3100, 5), 3);
  assert.equal(reflectionLeft(1000, 6000, 5), 0);
  assert.equal(reflectionLeft(1000, 99999, 5), 0);
});

test("questions du parcours : Windows ou Mac, refus qui imposent un nouveau plan", () => {
  assert.deepEqual(formatTravels(false), []);
  assert.deepEqual(formatTravels(true), ["windows", "macos"]);
  for (const code of ["format_token_expired", "format_token_used", "format_token_unknown", "format_identity_changed"]) assert.equal(needsNewPlan(code), true, code);
  for (const code of ["format_pin_invalid", "format_in_use", "format_confirmation_mismatch"]) assert.equal(needsNewPlan(code), false, code);
  assert.equal(refusalKey("format_in_use"), "storage.format.refusal.format_in_use");
});

test("pendant l'effacement on ne peut ni fermer ni annuler ; l'opération reste visible", () => {
  assert.equal(canLeaveWizard(null), true);
  assert.equal(canLeaveWizard({ state: "running", point_of_no_return: false }), false);
  assert.equal(canLeaveWizard({ state: "running", point_of_no_return: true }), false);
  assert.equal(canLeaveWizard({ state: "done", point_of_no_return: true }), true);
  assert.equal(formatFinished({ state: "running" }), false);
  assert.equal(formatFinished({ state: "failed" }), true);
  assert.equal(FORMAT_STEP_ORDER.indexOf("table") < FORMAT_STEP_ORDER.indexOf("format"), true);
  assert.equal(stepIcon("running"), "progress_activity");
});

test("un support en cours de formatage est « occupé » et n'offre plus d'exploration", () => {
  const v = { state: "formatting" as const, connected: true, health: null, library: null };
  assert.equal(volumeStatus(v), "busy");
  assert.equal(primaryAction(v), null);
});

type Dict = { [key: string]: string | Dict };
function codesOf(dict: Dict): string[] {
  return Object.keys(dict);
}

test("chaque code de refus du serveur est traduit en français et en anglais", () => {
  // Liste miroir de backend/app/storage/formatting/refusals.py (le test serveur vérifie que chaque code y est documenté).
  const codes = [
    "format_unsupported_platform", "format_tool_missing", "format_not_found", "format_not_allowed", "format_phone", "format_not_removable", "format_internal_disk",
    "format_system_disk", "format_bobine_data", "format_library_registered", "format_in_use", "format_busy_operation", "format_read_only", "format_encrypted_stack",
    "format_image_not_allowed", "format_too_small", "format_fs_unavailable", "format_fs_unknown", "format_label_invalid", "format_confirmation_mismatch",
    "format_ack_missing", "format_too_early", "format_token_missing", "format_token_unknown", "format_token_expired", "format_token_used", "format_token_owner",
    "format_identity_changed", "format_pin_required", "format_pin_invalid", "format_not_authorized", "format_busy_mounted", "format_cannot_cancel",
    "format_job_not_found", "format_failed",
  ];
  const fr = (dictionaries.fr.storage as Dict).format as Dict;
  const en = (dictionaries.en.storage as Dict).format as Dict;
  for (const code of codes) {
    assert.ok(typeof (fr.refusal as Dict)[code] === "string", `fr : ${code}`);
    assert.ok(typeof (en.refusal as Dict)[code] === "string", `en : ${code}`);
  }
  assert.deepEqual(codesOf(fr.refusal as Dict).sort(), codesOf(en.refusal as Dict).sort());
});

test("chaque étape du serveur a son texte", () => {
  const fr = ((dictionaries.fr.storage as Dict).format as Dict).steps as Dict;
  for (const step of FORMAT_STEP_ORDER) assert.ok(typeof fr[step] === "string", step);
});
