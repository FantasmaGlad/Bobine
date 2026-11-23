"use client";

import { useCallback, useSyncExternalStore } from "react";
import { readUrlView, withUrlView, type ViewParser } from "@/lib/urlView";

const URL_VIEW_EVENT = "bobine:url-view";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("popstate", onChange);
  window.addEventListener(URL_VIEW_EVENT, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(URL_VIEW_EVENT, onChange);
  };
}

export function useUrlView<T extends string>(param: string, parse: ViewParser<T>): [T, (next: T) => void] {
  const fallback = parse(null);
  const view = useSyncExternalStore(subscribe, () => readUrlView(window.location.search, param, parse), () => fallback);
  const choose = useCallback((next: T) => {
    const query = withUrlView(window.location.search, param, next, fallback);
    window.history.pushState(null, "", `${window.location.pathname}${query}${window.location.hash}`);
    window.dispatchEvent(new Event(URL_VIEW_EVENT));
  }, [param, fallback]);
  return [view, choose];
}
