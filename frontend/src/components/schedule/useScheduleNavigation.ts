"use client";

import { useEffect, useState } from "react";

import { addDays, getWeekStart } from "@/lib/scheduleTime";

import { startOfToday } from "./media";
import type { ScheduleView } from "./ScheduleToolbar";

export const ZOOM_LEVELS = [0.5, 0.8, 1.2, 1.8, 2.6];

export function useScheduleNavigation(isMobile: boolean) {
  const [view, setView] = useState<ScheduleView>("week");
  const [zoomIndex, setZoomIndex] = useState(2);
  const [day, setDay] = useState<Date>(startOfToday);
  const [weekStart, setWeekStart] = useState<Date>(() => getWeekStart(new Date()));

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronise avec le viewport (matchMedia)
    if (isMobile && view === "week") setView("day");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMobile]);

  useEffect(() => {
    if (view !== "day") return;
    const dayWeekStart = getWeekStart(day);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resynchronise la fenetre de fetch avec le jour affiche
    if (dayWeekStart.getTime() !== weekStart.getTime()) setWeekStart(dayWeekStart);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day, view]);

  const step = (direction: -1 | 1) => {
    if (view === "day") setDay((prev) => addDays(prev, direction));
    else setWeekStart((prev) => addDays(prev, 7 * direction));
  };

  const today = () => {
    if (view === "day") setDay(startOfToday());
    else setWeekStart(getWeekStart(new Date()));
  };

  const dayView = () => {
    if (day < weekStart || day >= addDays(weekStart, 7)) setDay(weekStart);
    setView("day");
  };

  const zoom = (direction: -1 | 1) => setZoomIndex((z) => Math.min(ZOOM_LEVELS.length - 1, Math.max(0, z + direction)));

  return { view, setView, zoomIndex, pxPerMinute: ZOOM_LEVELS[zoomIndex], day, weekStart, step, today, dayView, zoom };
}
