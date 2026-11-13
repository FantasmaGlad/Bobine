import { useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";

export function useServerClock(): Date | null {
  const [now, setNow] = useState<Date | null>(null);
  const clockOffsetRef = useRef(0);
  useEffect(() => {
    const syncClock = () => {
      fetch(getApiUrl("/time"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && typeof data.server_ts === "number") clockOffsetRef.current = data.server_ts - Date.now();
        })
        .catch(() => {});
    };
    syncClock();
    setNow(new Date(Date.now() + clockOffsetRef.current));
    const syncId = setInterval(syncClock, 60 * 1000);
    const tickId = setInterval(() => setNow(new Date(Date.now() + clockOffsetRef.current)), 1000);
    return () => {
      clearInterval(syncId);
      clearInterval(tickId);
    };
  }, []);
  return now;
}
