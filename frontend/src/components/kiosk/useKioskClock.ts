import { useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import type { NextCourse } from "./media";

export function useKioskClock(channel: "cable" | "network") {
  const [now, setNow] = useState(new Date());
  const clockOffsetRef = useRef<number>(0);
  const [nextCourse, setNextCourse] = useState<NextCourse | null>(null);
  const [, setFastTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setFastTick((t) => (t + 1) % 1_000_000), 200);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const syncClock = () => {
      fetch(getApiUrl("/time"), { cache: "no-store" })
        .then((res) => res.ok ? res.json() : null)
        .then((data) => {
          if (data && typeof data.server_ts === "number") {
            clockOffsetRef.current = data.server_ts - Date.now();
          }
        })
        .catch((err) => {
          console.warn("[clock] Synchronisation heure serveur échouée :", err);
        });
    };
    syncClock();
    const syncId = setInterval(syncClock, 60 * 1000);
    const tickId = setInterval(() => setNow(new Date(Date.now() + clockOffsetRef.current)), 1000);
    return () => {
      clearInterval(syncId);
      clearInterval(tickId);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const fetchNext = () => {
      fetch(getApiUrl(`/schedule/next?channel=${channel}`), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!cancelled) setNextCourse(data);
        })
        .catch(() => {
          if (!cancelled) setNextCourse(null);
        });
    };
    fetchNext();
    const id = setInterval(fetchNext, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [channel]);
  return { now, nextCourse };
}
