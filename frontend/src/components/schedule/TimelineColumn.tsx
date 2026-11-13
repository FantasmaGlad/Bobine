"use client";

import React from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { computeCutsPrevious, getOccurrenceWindow, isSameLocalDay, minutesToHHMM, MIN_BLOCK_MINUTES, MINUTES_PER_DAY, occurrenceKey, type Occurrence } from "@/lib/scheduleTime";

import { hourLabel } from "./media";
import TimelineBlock from "./TimelineBlock";
import type { ScheduleDrag } from "./useDrag";
import type { OccurrenceControls } from "./useOccurrenceControls";
import type { ScheduleCatalog } from "./useScheduleData";

interface Props {
  day: Date;
  dayIndex: number;
  occurrences: Occurrence[];
  pxPerMinute: number;
  drag: ScheduleDrag;
  controls: OccurrenceControls;
  catalog: ScheduleCatalog;
  onCreate: (day: Date) => void;
  onDrop: (dayIndex: number) => void;
}

function Band({ occurrence }: { occurrence: Occurrence }) {
  const { t } = useAppSettings();
  const label = occurrence.title ?? t("schedule.permanentAmbianceLabel");
  return (
    <div className="schedule-timeline-band-247" title={label} style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0 }}>
      <div className="schedule-timeline-band-247-label">
        <Icon name="graphic_eq" size={12} />
        <span>{label}</span>
      </div>
    </div>
  );
}

function Ghost({ drag, pxPerMinute }: { drag: ScheduleDrag; pxPerMinute: number }) {
  const minutes = drag.overMinutes!;
  const payload = drag.payload!;
  return (
    <div
      className="schedule-timeline-ghost"
      style={{ position: "absolute", top: minutes * pxPerMinute, height: Math.max(payload.durationMinutes, MIN_BLOCK_MINUTES) * pxPerMinute, left: 4, right: 4, zIndex: 2 }}
    >
      <span className="schedule-timeline-ghost-time">{minutesToHHMM(minutes)}</span>
      <span className="schedule-timeline-ghost-label">{payload.label}</span>
    </div>
  );
}

function snappedMinutes(e: React.DragEvent<HTMLDivElement>, pxPerMinute: number): number {
  const rect = e.currentTarget.getBoundingClientRect();
  const snapped = Math.round((e.clientY - rect.top) / pxPerMinute / 15) * 15;
  return Math.min(Math.max(snapped, 0), MINUTES_PER_DAY - 15);
}

export default function TimelineColumn({ day, dayIndex, occurrences, pxPerMinute, drag, controls, catalog, onCreate, onDrop }: Props) {
  const { t } = useAppSettings();
  const isToday = isSameLocalDay(day, new Date());
  const now = new Date();
  const bands = occurrences.filter((o) => getOccurrenceWindow(o).isBackgroundBand);
  const timed = occurrences.filter((o) => !getOccurrenceWindow(o).isBackgroundBand);
  const cuts = computeCutsPrevious(timed);
  const hourHeight = 60 * pxPerMinute;
  const ghost = drag.overDay === dayIndex && drag.overMinutes != null && drag.payload;

  return (
    <div className={`schedule-timeline-column ${isToday ? "today" : ""}`}>
      <div
        className={`schedule-timeline-track ${drag.overDay === dayIndex ? "drag-over" : ""}`}
        style={{ height: MINUTES_PER_DAY * pxPerMinute }}
        onClick={() => onCreate(day)}
        onDragOver={(e) => {
          e.preventDefault();
          drag.hover(dayIndex, snappedMinutes(e, pxPerMinute));
        }}
        onDragLeave={drag.leave}
        onDrop={() => onDrop(dayIndex)}
      >
        {bands.map((o) => <Band key={occurrenceKey(o)} occurrence={o} />)}
        {Array.from({ length: 24 }, (_, hour) => (
          <div key={hour} className="schedule-timeline-hour-row" style={{ height: hourHeight }}>
            <span className="schedule-timeline-hour-label">{hourLabel(hour)}</span>
          </div>
        ))}
        {isToday && (
          <div className="schedule-timeline-now-line" style={{ top: (now.getHours() * 60 + now.getMinutes()) * pxPerMinute }} title={t("schedule.today")}>
            <span className="schedule-timeline-now-dot" />
          </div>
        )}
        {timed.map((o) => {
          const win = getOccurrenceWindow(o);
          const key = occurrenceKey(o);
          return (
            <TimelineBlock
              key={key}
              occurrence={o}
              style={{ position: "absolute", top: win.startMin * pxPerMinute, height: win.durationMin * pxPerMinute, left: 4, right: 4, zIndex: 1 }}
              cutsPrevious={cuts.has(key)}
              controls={controls}
              catalog={catalog}
            />
          );
        })}
        {ghost && <Ghost drag={drag} pxPerMinute={pxPerMinute} />}
      </div>
    </div>
  );
}
