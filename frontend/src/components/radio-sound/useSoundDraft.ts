import { useEffect, useRef, useState } from "react";
import { clampSound, matchingPreset, type RadioSoundSettings } from "@/lib/radioSound";

const SEND_DELAY_MS = 120;
const DRAFT_HOLD_MS = 600;

export function useSoundDraft(sound: RadioSoundSettings, sendCommand: (command: string, params?: Record<string, unknown>) => void) {
  const [draft, setDraft] = useState<RadioSoundSettings | null>(null);
  const sendTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const current = draft ?? sound;

  useEffect(
    () => () => {
      if (sendTimerRef.current) clearTimeout(sendTimerRef.current);
      if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    },
    [],
  );

  const commit = (next: RadioSoundSettings) => {
    const bounded = clampSound(next, current);
    setDraft(bounded);
    if (sendTimerRef.current) clearTimeout(sendTimerRef.current);
    sendTimerRef.current = setTimeout(() => {
      sendCommand("radio_set_sound", { sound: bounded });
      if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
      holdTimerRef.current = setTimeout(() => setDraft(null), DRAFT_HOLD_MS);
    }, SEND_DELAY_MS);
  };

  const setManual = (patch: Partial<RadioSoundSettings>) => {
    const merged = clampSound(patch, current);
    commit({ ...merged, preset: matchingPreset(merged) });
  };

  return { current, commit, setManual };
}
