"use client";

import { useEffect, useState } from "react";
import { reflectionLeft } from "@/lib/storage/format";
import type { Stage } from "./useFormatPlan";

const REFLECTION_SECONDS = 5;

export function useConfirmClock(stage: Stage, setStage: (stage: Stage) => void) {
  const [typed, setTyped] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  const [now, setNow] = useState(0);

  useEffect(() => {
    if (stage !== "confirm") return;
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [stage]);

  const toConfirm = () => {
    setTyped("");
    setAcknowledged(false);
    const start = Date.now();
    setStartedAt(start);
    setNow(start);
    setStage("confirm");
  };

  const secondsLeft = reflectionLeft(startedAt, now || startedAt, REFLECTION_SECONDS);
  return { typed, setTyped, acknowledged, setAcknowledged, secondsLeft, toConfirm };
}
