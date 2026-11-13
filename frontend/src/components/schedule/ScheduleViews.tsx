"use client";

import React from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { isSameLocalDay, MINUTES_PER_DAY, occurrenceKey, type Occurrence } from "@/lib/scheduleTime";

import { hourLabel } from "./media";
import OccurrenceChip from "./OccurrenceChip";
import TimelineColumn from "./TimelineColumn";
import type { ScheduleDrag } from "./useDrag";
import type { OccurrenceControls } from "./useOccurrenceControls";
import type { ScheduleCatalog } from "./useScheduleData";

export interface ViewProps {
  weekDays: Date[];
  byDay: Occurrence[][];
  pxPerMinute: number;
  drag: ScheduleDrag;
  controls: OccurrenceControls;
  catalog: ScheduleCatalog;
  onCreate: (day: Date) => void;
  onDrop: (dayIndex: number) => void;
}

function TimeAxis({ pxPerMinute }: { pxPerMinute: number }) {
  return (
    <div className="schedule-timeline-time-axis">
      <div className="schedule-axis-header">
        <Icon name="schedule" size={16} />
      </div>
      <div className="schedule-timeline-axis-track" style={{ height: MINUTES_PER_DAY * pxPerMinute }}>
        {Array.from({ length: 24 }, (_, hour) => (
          <div key={hour} className="schedule-timeline-axis-hour" style={{ height: 60 * pxPerMinute }}>
            <span>{hourLabel(hour)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const column = (props: ViewProps, day: Date, index: number) => (
  <TimelineColumn
    day={day}
    dayIndex={index}
    occurrences={props.byDay[index] ?? []}
    pxPerMinute={props.pxPerMinute}
    drag={props.drag}
    controls={props.controls}
    catalog={props.catalog}
    onCreate={props.onCreate}
    onDrop={props.onDrop}
  />
);

export const WeekView = React.forwardRef<HTMLDivElement, ViewProps>(function WeekView(props, ref) {
  const { tList } = useAppSettings();
  const names = tList("schedule.dayLabelsFull");
  const today = new Date();
  return (
    <div className="schedule-timeline-scroll" ref={ref}>
      <div className="schedule-timeline-week-grid">
        <TimeAxis pxPerMinute={props.pxPerMinute} />
        {props.weekDays.map((day, index) => (
          <div key={index} className={`schedule-timeline-week-col ${isSameLocalDay(day, today) ? "today" : ""}`}>
            <div className="schedule-day-header">
              <span className="schedule-day-header-name">{names[index]}</span>
              <span className="schedule-day-header-date">{day.getDate()}</span>
            </div>
            {column(props, day, index)}
          </div>
        ))}
      </div>
    </div>
  );
});

export const DayView = React.forwardRef<HTMLDivElement, ViewProps & { day: Date }>(function DayView(props, ref) {
  const index = props.weekDays.findIndex((d) => isSameLocalDay(d, props.day));
  return (
    <div className="schedule-timeline-scroll" ref={ref}>
      <div className="schedule-timeline-day-single">{column(props, props.day, index)}</div>
    </div>
  );
});

export function ListView({ weekDays, byDay, controls, catalog }: Pick<ViewProps, "weekDays" | "byDay" | "controls" | "catalog">) {
  const { t, tList } = useAppSettings();
  const names = tList("schedule.dayLabelsFull");
  if (byDay.every((day) => day.length === 0)) {
    return (
      <div className="schedule-list-scroll">
        <div style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>{t("schedule.noScheduleThisWeek")}</div>
      </div>
    );
  }
  return (
    <div className="schedule-list-scroll">
      {weekDays.map((day, index) =>
        byDay[index].length === 0 ? null : (
          <div key={index} className="schedule-list-day-group">
            <div className="schedule-list-day-label">{names[index]} {day.getDate()}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {byDay[index].map((o) => <OccurrenceChip key={occurrenceKey(o)} occurrence={o} controls={controls} catalog={catalog} />)}
            </div>
          </div>
        )
      )}
    </div>
  );
}
