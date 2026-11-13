"use client";

import React from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMinutes } from "@/lib/format";
import { formatOccurrenceTime, getOccurrenceWindow, occurrenceKey, type Occurrence } from "@/lib/scheduleTime";

import { occurrenceThumb } from "./media";
import OccurrenceActions from "./OccurrenceActions";
import OccurrenceBadges from "./OccurrenceBadges";
import type { OccurrenceControls } from "./useOccurrenceControls";
import type { ScheduleCatalog } from "./useScheduleData";

interface Props {
  occurrence: Occurrence;
  style: React.CSSProperties;
  cutsPrevious: boolean;
  controls: OccurrenceControls;
  catalog: ScheduleCatalog;
}

const TARGET_ICONS = { radio_playlist: "graphic_eq", playlist: "playlist_play", video: "movie" } as const;

function timeLabel(o: Occurrence): string {
  const start = formatOccurrenceTime(o.run_at);
  if (o.target_type !== "radio_playlist") return `${start} · ${formatMinutes(o.duration_seconds)}`;
  return o.end_time ? `${start}–${o.end_time}` : start;
}

export default function TimelineBlock({ occurrence: o, style, cutsPrevious, controls, catalog }: Props) {
  const { t } = useAppSettings();
  const key = occurrenceKey(o);
  const thumb = occurrenceThumb(o);
  return (
    <div
      className={`schedule-timeline-block ${o.override_action === "cancelled" ? "cancelled" : ""} ${cutsPrevious ? "cuts-previous" : ""}`}
      style={style}
      title={cutsPrevious ? t("schedule.overlapTooltip") : undefined}
      onClick={(e) => {
        e.stopPropagation();
        controls.toggle(key);
      }}
    >
      <div className="schedule-timeline-block-thumb">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt="" />
        ) : (
          <Icon name={TARGET_ICONS[o.target_type] ?? "movie"} size={18} style={{ opacity: 0.35 }} />
        )}
        {cutsPrevious && (
          <span className="schedule-timeline-cut-badge">
            <Icon name="content_cut" size={11} />
          </span>
        )}
      </div>
      <div className="schedule-timeline-block-body">
        <div className="schedule-timeline-block-title">{o.title ?? t("schedule.targetNotFound")}</div>
        <div className="schedule-timeline-block-time">{timeLabel(o)}</div>
        <OccurrenceBadges occurrence={o} />
      </div>
      {controls.expandedKey === key && !getOccurrenceWindow(o).isBackgroundBand && (
        <OccurrenceActions occurrence={o} occurrenceKey={key} controls={controls} catalog={catalog} />
      )}
    </div>
  );
}
