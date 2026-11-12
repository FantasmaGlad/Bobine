import { test } from "node:test";
import assert from "node:assert/strict";
import { computeCutsPrevious, getOccurrenceWindow, getWeekStart, MIN_BLOCK_MINUTES, MINUTES_PER_DAY, type Occurrence } from "../src/lib/scheduleTime.ts";

function occurrence(runAt: string, patch: Partial<Occurrence> = {}): Occurrence {
  return {
    schedule_id: 1, schedule_type: "once", run_at: runAt, target_type: "video", target_id: 1, title: null, program: null,
    duration_seconds: 2700, thumbnail_path: null, cover_track_id: null, end_time: null, is_24_7: false,
    is_override: false, override_action: null, override_id: null, ...patch,
  };
}

test("la semaine commence le lundi, dimanche compris", () => {
  assert.equal(getWeekStart(new Date(2026, 10, 15, 22)).getDate(), 9);
  assert.equal(getWeekStart(new Date(2026, 10, 9, 8)).getDate(), 9);
});

test("fenêtre d'une occurrence : durée du média, bande de fond pour la radio continue", () => {
  const start = new Date(2026, 10, 12, 18, 0).toISOString();
  assert.deepEqual(getOccurrenceWindow(occurrence(start)), { startMin: 1080, durationMin: 45, isBackgroundBand: false });
  assert.equal(getOccurrenceWindow(occurrence(start, { duration_seconds: null })).durationMin, MIN_BLOCK_MINUTES);
  const radio = getOccurrenceWindow(occurrence(start, { target_type: "radio_playlist", is_24_7: true }));
  assert.deepEqual(radio, { startMin: 0, durationMin: MINUTES_PER_DAY, isBackgroundBand: true });
});

test("une occurrence qui commence avant la fin de la précédente la coupe", () => {
  const first = occurrence(new Date(2026, 10, 12, 18, 0).toISOString(), { schedule_id: 1 });
  const second = occurrence(new Date(2026, 10, 12, 18, 30).toISOString(), { schedule_id: 2 });
  assert.equal(computeCutsPrevious([first, second]).size, 1);
});
