"use client";

import { useState } from "react";

import type { DragPayload } from "./media";

export function useScheduleDrag() {
  const [payload, setPayload] = useState<DragPayload | null>(null);
  const [overDay, setOverDay] = useState<number | null>(null);
  const [overMinutes, setOverMinutes] = useState<number | null>(null);

  const hover = (day: number, minutes: number) => {
    setOverDay(day);
    setOverMinutes(minutes);
  };

  const leave = () => {
    setOverDay(null);
    setOverMinutes(null);
  };

  const end = () => {
    setPayload(null);
    leave();
  };

  return { payload, overDay, overMinutes, start: setPayload, hover, leave, end };
}

export type ScheduleDrag = ReturnType<typeof useScheduleDrag>;
