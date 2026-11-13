"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatWeekLabel } from "@/lib/scheduleTime";

export type ScheduleView = "day" | "week" | "list";

interface Props {
  view: ScheduleView;
  onView: (view: ScheduleView) => void;
  onDayView: () => void;
  weekStart: Date;
  day: Date;
  onStep: (direction: -1 | 1) => void;
  onToday: () => void;
  zoomIndex: number;
  zoomLevels: number;
  onZoom: (direction: -1 | 1) => void;
  isMobile: boolean;
  showLibraryToggle: boolean;
  libraryOpen: boolean;
  onToggleLibrary: () => void;
  onCreate: () => void;
}

function Navigation({ view, weekStart, day, onStep, onToday }: Pick<Props, "view" | "weekStart" | "day" | "onStep" | "onToday">) {
  const { t, tList, language } = useAppSettings();
  const isDay = view === "day";
  const label = isDay
    ? `${tList("schedule.dayLabelsFull")[(day.getDay() + 6) % 7]} ${day.toLocaleDateString(language === "fr" ? "fr-FR" : "en-US", { day: "numeric", month: "short" })}`
    : formatWeekLabel(weekStart, language);
  return (
    <div className="week-nav">
      <button className="btn btn-secondary btn-sm" onClick={() => onStep(-1)} title={t(isDay ? "schedule.previousDayTitle" : "schedule.previousWeekTitle")}>
        <Icon name="chevron_left" size={16} />
        <span className="week-nav-btn-text">{t("schedule.previousWeekShort")}</span>
      </button>
      <button className="btn btn-secondary btn-sm" onClick={onToday}>{t("schedule.today")}</button>
      <button className="btn btn-secondary btn-sm" onClick={() => onStep(1)} title={t(isDay ? "schedule.nextDayTitle" : "schedule.nextWeekTitle")}>
        <span className="week-nav-btn-text">{t("schedule.nextWeekShort")}</span>
        <Icon name="chevron_right" size={16} />
      </button>
      <span className="week-nav-label">{label}</span>
    </div>
  );
}

function Zoom({ zoomIndex, zoomLevels, onZoom }: Pick<Props, "zoomIndex" | "zoomLevels" | "onZoom">) {
  const { t } = useAppSettings();
  return (
    <div className="view-toggle" title={t("schedule.zoomTitle")}>
      <button type="button" className="view-btn olc-press" onClick={() => onZoom(-1)} disabled={zoomIndex === 0} title={t("schedule.zoomOutTitle")} style={{ padding: "4px 8px" }}>
        <Icon name="zoom_out" size={16} />
      </button>
      <button type="button" className="view-btn olc-press" onClick={() => onZoom(1)} disabled={zoomIndex === zoomLevels - 1} title={t("schedule.zoomInTitle")} style={{ padding: "4px 8px" }}>
        <Icon name="zoom_in" size={16} />
      </button>
    </div>
  );
}

function ViewButtons({ view, onView, onDayView, isMobile }: Pick<Props, "view" | "onView" | "onDayView" | "isMobile">) {
  const { t } = useAppSettings();
  const button = (mode: ScheduleView, icon: string, title: string, onClick: () => void) => (
    <button className={`view-btn olc-press ${view === mode ? "active" : ""}`} onClick={onClick} title={t(title)} style={{ padding: "4px 10px" }}>
      <Icon name={icon} size={17} />
    </button>
  );
  return (
    <div className="view-toggle">
      {button("day", "view_day", "schedule.dayView", onDayView)}
      {!isMobile && button("week", "calendar_view_week", "schedule.weekView", () => onView("week"))}
      {button("list", "view_list", "schedule.listView", () => onView("list"))}
    </div>
  );
}

export default function ScheduleToolbar(props: Props) {
  const { t } = useAppSettings();
  return (
    <div className="schedule-toolbar sticky-glass-toolbar">
      <Navigation {...props} />
      <div style={{ display: "flex", gap: "8px", alignItems: "center", flexShrink: 0 }}>
        {props.view !== "list" && <Zoom {...props} />}
        <ViewButtons {...props} />
        {props.showLibraryToggle && (
          <button
            type="button"
            className={`view-btn olc-press ${props.libraryOpen ? "active" : ""}`}
            onClick={props.onToggleLibrary}
            title={t("schedule.quickLibrary")}
            style={{ display: "inline-flex", alignItems: "center", gap: "6px", height: "34px", padding: "0 10px", borderRadius: "var(--radius-sm)", flexShrink: 0 }}
          >
            <Icon name="video_library" size={16} />
            <span className="hidden-sm">{t("nav.library")}</span>
          </button>
        )}
        <button className="btn btn-primary" onClick={props.onCreate} style={{ height: "34px", padding: "0 12px", fontSize: "0.85rem", whiteSpace: "nowrap", flexShrink: 0 }}>
          <Icon name="add" size={18} />
          <span className="schedule-btn-text-full">{t("schedule.newSchedule")}</span>
          <span className="schedule-btn-text-short">{t("schedule.newScheduleShort")}</span>
        </button>
      </div>
    </div>
  );
}
