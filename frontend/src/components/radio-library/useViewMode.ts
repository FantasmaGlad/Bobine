"use client";

import { useClientChoice } from "@/lib/useClientSnapshot";

import type { ViewMode } from "./types";

const STORAGE_KEY = "bobine.radioLibrary.view";

function readStoredMode(): ViewMode | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "grid" || stored === "list") return stored;
  } catch {
  }
  return null;
}

export function useViewMode() {
  const [mode, setMode] = useClientChoice<ViewMode>(readStoredMode, "grid");

  const choose = (next: ViewMode) => {
    setMode(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
    }
  };

  return [mode, choose] as const;
}
