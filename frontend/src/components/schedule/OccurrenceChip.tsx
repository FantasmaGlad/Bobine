"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatOccurrenceTime, occurrenceKey, type Occurrence } from "@/lib/scheduleTime";

import OccurrenceActions from "./OccurrenceActions";
import OccurrenceBadges from "./OccurrenceBadges";
import type { OccurrenceControls } from "./useOccurrenceControls";
import type { ScheduleCatalog } from "./useScheduleData";

interface Props {
  occurrence: Occurrence;
  controls: OccurrenceControls;
  catalog: ScheduleCatalog;
}

export default function OccurrenceChip({ occurrence: o, controls, catalog }: Props) {
  const { t, tList } = useAppSettings();
  const key = occurrenceKey(o);
  const dayName = tList("schedule.dayLabelsFull")[(new Date(o.run_at).getDay() + 6) % 7];
  return (
    <div
      className={`schedule-occurrence-chip ${o.override_action === "cancelled" ? "cancelled" : ""}`}
      style={{ borderLeftColor: "var(--accent-primary)" }}
      onClick={(e) => {
        e.stopPropagation();
        controls.toggle(key);
      }}
    >
      <div className="schedule-occurrence-time">
        {formatOccurrenceTime(o.run_at)}
        {` · ${dayName}`}
      </div>
      <div className="schedule-occurrence-title">{o.title ?? t("schedule.targetNotFound")}</div>
      <OccurrenceBadges occurrence={o} />
      {controls.expandedKey === key && <OccurrenceActions occurrence={o} occurrenceKey={key} controls={controls} catalog={catalog} />}
    </div>
  );
}
