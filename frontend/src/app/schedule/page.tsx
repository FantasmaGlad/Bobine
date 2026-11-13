"use client";

import { useEffect, useRef, useState } from "react";

import PageNav from "@/components/PageNav";
import QuickLibrary from "@/components/schedule/QuickLibrary";
import ScheduleDrawer, { DeleteScheduleDialog } from "@/components/schedule/ScheduleDrawer";
import ScheduleToolbar from "@/components/schedule/ScheduleToolbar";
import { DayView, ListView, WeekView, type ViewProps } from "@/components/schedule/ScheduleViews";
import { useScheduleDrag } from "@/components/schedule/useDrag";
import { useOccurrenceControls } from "@/components/schedule/useOccurrenceControls";
import { useCableOutput, useOccurrences, useScheduleCatalog } from "@/components/schedule/useScheduleData";
import { useScheduleForm } from "@/components/schedule/useScheduleForm";
import { useScheduleNavigation, ZOOM_LEVELS } from "@/components/schedule/useScheduleNavigation";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { isRadioLane, parseScheduleChannel } from "@/lib/scheduleChannels";
import type { ChannelValue } from "@/lib/scheduleTime";
import { useIsMobile } from "@/lib/useIsMobile";
import { useToast } from "@/lib/useToast";

const CHANNEL_TABS = [
  { id: "cable", icon: "cable", label: "schedule.channelTabCable" },
  { id: "network", icon: "wifi", label: "schedule.channelTabNetwork" },
  { id: "radio_cable", icon: "graphic_eq", label: "schedule.channelTabRadioCable" },
  { id: "radio_network", icon: "graphic_eq", label: "schedule.channelTabRadioNetwork" },
];

function initialChannel(): ChannelValue {
  if (typeof window === "undefined") return "cable";
  return parseScheduleChannel(new URLSearchParams(window.location.search).get("channel"));
}

export default function SchedulePage() {
  const isMobile = useIsMobile();
  const { t } = useAppSettings();
  const [channel, setChannel] = useState<ChannelValue>(initialChannel);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const scroll = useRef<HTMLDivElement | null>(null);
  const { toast, showToast } = useToast();
  const nav = useScheduleNavigation(isMobile);
  const catalog = useScheduleCatalog();
  const cableOutput = useCableOutput(channel);
  const data = useOccurrences(nav.weekStart, channel, showToast);
  const form = useScheduleForm(channel, showToast, data.refresh);
  const controls = useOccurrenceControls(showToast, data.refresh, form.openEdit);
  const drag = useScheduleDrag();
  const radio = isRadioLane(channel);

  const [wasMobile, setWasMobile] = useState(isMobile);
  if (wasMobile !== isMobile) {
    setWasMobile(isMobile);
    if (isMobile) setLibraryOpen(false);
  }

  useEffect(() => {
    if ((nav.view === "week" || nav.view === "day") && scroll.current) scroll.current.scrollTop = Math.max(0, 450 * nav.pxPerMinute - 20);
  }, [nav.view, channel, nav.pxPerMinute]);

  const dropOnDay = (dayIndex: number) => {
    const minutes = drag.overMinutes;
    drag.leave();
    if (!drag.payload) return;
    const date = new Date(data.weekDays[dayIndex]);
    if (minutes != null) date.setHours(0, minutes, 0, 0);
    form.openCreate(date, drag.payload, minutes != null);
    drag.start(null);
  };

  const viewProps: ViewProps = {
    weekDays: data.weekDays, byDay: data.byDay, pxPerMinute: nav.pxPerMinute, drag, controls, catalog,
    onCreate: (day) => form.openCreate(day), onDrop: dropOnDay,
  };

  const body = data.loading ? (
    <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>{t("schedule.loadingSchedule")}</div>
  ) : nav.view === "week" ? (
    <WeekView ref={scroll} {...viewProps} />
  ) : nav.view === "day" ? (
    <DayView ref={scroll} {...viewProps} day={nav.day} />
  ) : (
    <ListView {...viewProps} />
  );

  return (
    <div className="schedule-page">
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
      <PageNav
        tabs={CHANNEL_TABS.map((tab) => ({ ...tab, label: t(tab.label) }))}
        value={channel}
        onChange={(id) => setChannel(id as ChannelValue)}
        ariaLabel={t("schedule.channelCableTitle")}
      />
      <ScheduleToolbar
        view={nav.view}
        onView={nav.setView}
        onDayView={nav.dayView}
        weekStart={nav.weekStart}
        day={nav.day}
        onStep={nav.step}
        onToday={nav.today}
        zoomIndex={nav.zoomIndex}
        zoomLevels={ZOOM_LEVELS.length}
        onZoom={nav.zoom}
        isMobile={isMobile}
        showLibraryToggle={!radio}
        libraryOpen={libraryOpen}
        onToggleLibrary={() => setLibraryOpen((open) => !open)}
        onCreate={() => form.openCreate()}
      />
      {channel === "radio_cable" && cableOutput !== null && cableOutput !== "radio" && (
        <div className="interrupted-block" role="status">
          <div className="interrupted-text">
            <span className="interrupted-label">{t("schedule.radioCableAutoSwitchHint")}</span>
          </div>
        </div>
      )}
      <div className="schedule-body" style={{ flexDirection: isMobile ? "column" : "row", gap: "20px" }}>
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0 }}>{body}</div>
        {libraryOpen && (
          <QuickLibrary radio={radio} catalog={catalog} drag={drag} isMobile={isMobile} onClose={() => setLibraryOpen(false)} onPick={(preset) => form.openCreate(undefined, preset)} />
        )}
      </div>
      {form.open && <ScheduleDrawer radio={radio} catalog={catalog} state={form} />}
      {form.confirmDelete && <DeleteScheduleDialog onConfirm={form.remove} onCancel={() => form.setConfirmDelete(false)} />}
    </div>
  );
}
