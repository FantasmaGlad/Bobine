"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";

import type { ScheduleFormState } from "./useScheduleForm";

const CHECK_ROW = { flexDirection: "row", alignItems: "center", gap: "10px" } as const;

function RadioWindow({ state }: { state: ScheduleFormState }) {
  const { t } = useAppSettings();
  const { form, patch } = state;
  return (
    <>
      <div className="form-group" style={CHECK_ROW}>
        <input type="checkbox" checked={form.is24_7} onChange={(e) => patch({ is24_7: e.target.checked })} style={{ width: "18px", height: "18px" }} />
        <label className="form-label" style={{ margin: 0 }}>{t("schedule.is247Label")}</label>
      </div>
      {!form.is24_7 && (
        <div className="form-group">
          <label className="form-label">{t("schedule.endTimeLabel")}</label>
          <input type="time" className="form-control" value={form.endTime} onChange={(e) => patch({ endTime: e.target.value })} />
          <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: "4px 0 0" }}>{t("schedule.endTimeHint")}</p>
        </div>
      )}
    </>
  );
}

function Recurring({ state }: { state: ScheduleFormState }) {
  const { t, tList } = useAppSettings();
  const { form, patch } = state;
  return (
    <>
      <div className="form-group">
        <label className="form-label">{t("schedule.daysOfWeekLabel")}</label>
        <div className="speed-group" style={{ width: "100%" }}>
          {tList("schedule.dayLabels").map((label, idx) => (
            <button key={idx} type="button" className={`speed-btn ${form.daysOfWeek.includes(idx) ? "active" : ""}`} style={{ flex: 1 }} onClick={() => state.toggleDay(idx)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">{t("schedule.hourLabel")}</label>
        <input type="time" className="form-control" value={form.time} onChange={(e) => patch({ time: e.target.value })} />
      </div>
      {form.targetType === "radio_playlist" && <RadioWindow state={state} />}
    </>
  );
}

export default function WhenFields({ state }: { state: ScheduleFormState }) {
  const { t } = useAppSettings();
  const { form, patch } = state;
  const typeButton = (value: "once" | "recurring", label: string) => (
    <button type="button" className={`speed-btn ${form.scheduleType === value ? "active" : ""}`} style={{ flex: 1 }} onClick={() => patch({ scheduleType: value })}>
      {t(label)}
    </button>
  );
  return (
    <>
      <div className="form-group">
        <label className="form-label">{t("schedule.scheduleTypeLabel")}</label>
        <div className="speed-group" style={{ width: "100%" }}>
          {typeButton("once", "schedule.onceOption")}
          {typeButton("recurring", "schedule.recurringOption")}
        </div>
      </div>
      {form.scheduleType === "once" ? (
        <div className="form-group">
          <label className="form-label">{t("schedule.dateTimeLabel")}</label>
          <input type="datetime-local" className="form-control" value={form.dateTime} onChange={(e) => patch({ dateTime: e.target.value })} />
        </div>
      ) : (
        <Recurring state={state} />
      )}
      <div className="form-group" style={CHECK_ROW}>
        <input type="checkbox" checked={form.active} onChange={(e) => patch({ active: e.target.checked })} style={{ width: "18px", height: "18px" }} />
        <label className="form-label" style={{ margin: 0 }}>{t("schedule.activeLabel")}</label>
      </div>
    </>
  );
}
