"use client";

import { useEffect, useState } from "react";
import { Scrubber } from "@/lib/scrub";

export function useScrubber(): Scrubber {
  const [scrubber] = useState(() => new Scrubber({
    now: () => performance.now(),
    setTimer: (run, delay) => window.setTimeout(run, delay),
    clearTimer: (id) => window.clearTimeout(id as number),
  }));
  useEffect(() => () => scrubber.cancel(), [scrubber]);
  return scrubber;
}
