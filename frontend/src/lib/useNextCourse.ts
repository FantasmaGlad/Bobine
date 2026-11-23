"use client";

import { useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { occurrencesPath, upcomingOnly, type UpcomingOccurrence } from "@/lib/upcoming";

export function useNextCourse(channel: string, refreshMs = 30000): UpcomingOccurrence | null {
  const [next, setNext] = useState<UpcomingOccurrence | null>(null);
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch(getApiUrl(occurrencesPath(channel, new Date())), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : []))
        .then((items: UpcomingOccurrence[]) => { if (!cancelled) setNext(upcomingOnly(items, 1)[0] ?? null); })
        .catch((error: unknown) => {
          console.warn("[prochainement] occurrences illisibles", error);
          if (!cancelled) setNext(null);
        });
    };
    load();
    const id = setInterval(load, refreshMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [channel, refreshMs]);
  return next;
}
