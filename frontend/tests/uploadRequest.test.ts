import { test } from "node:test";
import assert from "node:assert/strict";
import { CHUNKED_KINDS, UPLOAD_ENDPOINTS, buildFormData } from "../src/lib/uploads/request.ts";
import { progressReporter } from "../src/lib/uploads/progress.ts";
import type { UploadTask } from "../src/lib/uploads/types.ts";

function task(patch: Partial<UploadTask>): UploadTask {
  return { id: "t", status: "pending", progress: 0, kind: "video", title: "Cours", ...patch };
}

test("chaque type d'envoi a sa route et les envois découpés visent des fichiers uniques", () => {
  assert.equal(UPLOAD_ENDPOINTS.radio_files, "/radio/tracks/upload");
  assert.equal(CHUNKED_KINDS.has("audio_files"), false);
  assert.equal(CHUNKED_KINDS.has("video"), true);
});

test("un envoi repris ne transmet que l'identifiant et les métadonnées", () => {
  const file = new File(["x"], "a.mp4");
  const form = buildFormData(task({ file, program: "RPM", release: "", subtitles: [new File(["s"], "a.srt")] }), "U-1");
  assert.equal(form.get("upload_id"), "U-1");
  assert.equal(form.get("file"), null);
  assert.equal(form.get("program"), "RPM");
  assert.equal(form.get("release"), null);
  assert.equal(form.getAll("subtitles").length, 1);
});

test("plusieurs fichiers partent sous la même clé, sans métadonnées de cours pour la radio", () => {
  const files = [new File(["a"], "a.mp3"), new File(["b"], "b.mp3")];
  const form = buildFormData(task({ kind: "radio_files", files, program: "RPM" }));
  assert.equal(form.getAll("files").length, 2);
  assert.equal(form.get("program"), null);
  assert.equal(form.get("title"), "Cours");
});

test("la progression est limitée en fréquence sauf à la fin et donne une durée restante", () => {
  const patches: Partial<UploadTask>[] = [];
  let clock = 0;
  const report = progressReporter((p) => patches.push(p), () => clock);
  clock = 1000;
  report(10, 100);
  clock = 1100;
  report(20, 100);
  clock = 1200;
  report(100, 100);
  assert.deepEqual(patches.map((p) => p.progress), [10, 100]);
  assert.equal(patches[0].uploadEtaSeconds, 9);
  report(5, 0);
  assert.equal(patches.length, 2);
});
