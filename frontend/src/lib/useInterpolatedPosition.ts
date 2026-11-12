"use client";

import { useEffect, useRef, useState } from "react";

const MAX_EXTRAPOLATION_MS = 6000;
export function useInterpolatedPosition(
  serverPosition: number,
  playing: boolean,
  cause: string,
): number {
  const baselineRef = useRef({ value: serverPosition, receivedAt: 0 });
  const [display, setDisplay] = useState(serverPosition);

  useEffect(() => {
    let value = serverPosition;
    if (cause === "position_tick" && playing) {
      const prev = baselineRef.current;
      const extrapolated = prev.value + (Date.now() - prev.receivedAt) / 1000;
      value = Math.max(serverPosition, extrapolated);
    }
    baselineRef.current = { value, receivedAt: Date.now() };
    setDisplay(value);
  }, [serverPosition, playing, cause]);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      const { value, receivedAt } = baselineRef.current;
      const elapsedMs = Math.min(Date.now() - receivedAt, MAX_EXTRAPOLATION_MS);
      setDisplay(value + elapsedMs / 1000);
    }, 200);
    return () => clearInterval(id);
  }, [playing]);

  return display;
}
