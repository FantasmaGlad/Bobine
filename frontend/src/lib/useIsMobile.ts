"use client";

import { useCallback, useSyncExternalStore } from "react";

export function useIsMobile(breakpoint = 768): boolean {
  const query = `(max-width: ${breakpoint}px)`;
  const subscribe = useCallback((notify: () => void) => {
    const mql = window.matchMedia(query);
    mql.addEventListener("change", notify);
    return () => mql.removeEventListener("change", notify);
  }, [query]);
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false);
}
