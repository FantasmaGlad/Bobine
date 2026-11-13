import { useEffect, useRef } from "react";
import { getApiUrl } from "@/lib/apiUrl";

const DUCK_LEVEL_DEFAULT = 15;
const DUCK_FADE_MS_DEFAULT = 1500;

export function useDuckSettings() {
  const duckSettingsRef = useRef({ level: DUCK_LEVEL_DEFAULT, fadeMs: DUCK_FADE_MS_DEFAULT });
  useEffect(() => {
    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        duckSettingsRef.current = {
          level: typeof data.radio_announcement_duck_level === "number" ? data.radio_announcement_duck_level : DUCK_LEVEL_DEFAULT,
          fadeMs: typeof data.radio_announcement_fade_ms === "number" ? data.radio_announcement_fade_ms : DUCK_FADE_MS_DEFAULT,
        };
      })
      .catch(() => {});
  }, []);
  return duckSettingsRef;
}
