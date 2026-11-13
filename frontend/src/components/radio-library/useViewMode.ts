"use client";

import { useEffect, useState } from "react";

import type { ViewMode } from "./types";

const STORAGE_KEY = "bobine.radioLibrary.view";

export function useViewMode() {
  const [mode, setMode] = useState<ViewMode>("grid");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture unique d'une preference locale apres hydratation
      if (stored === "grid" || stored === "list") setMode(stored);
    } catch {
    }
  }, []);

  const choose = (next: ViewMode) => {
    setMode(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
    }
  };

  return [mode, choose] as const;
}
