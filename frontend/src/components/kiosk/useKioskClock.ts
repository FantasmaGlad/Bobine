import { useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { useNextCourse } from "@/lib/useNextCourse";
import type { OutputId } from "@/lib/outputs";

export function useKioskClock(channel: OutputId) {
  const [now, setNow] = useState(new Date());
  const clockOffsetRef = useRef<number>(0);
  const nextCourse = useNextCourse(channel);

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

  return { now, nextCourse };
}
