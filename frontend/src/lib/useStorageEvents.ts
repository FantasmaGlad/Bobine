"use client";

import { useCallback } from "react";
import { useServerEvent, type ServerMessage } from "./useServerEvent.ts";

export interface StorageEvent {
  scope: string;
  changes: string[];
}

export function isPlugEvent(event: StorageEvent): boolean {
  return event.scope === "volumes" && event.changes.some((c) => c === "added" || c === "removed" || c === "removed_abruptly");
}

export function useStorageEvents(onChange: (event: StorageEvent) => void, enabled = true): void {
  const onMessage = useCallback((data: ServerMessage) => {
    onChange({ scope: String(data.scope ?? ""), changes: Array.isArray(data.changes) ? data.changes.map(String) : [] });
  }, [onChange]);
  useServerEvent("storage_changed", onMessage, enabled);
}
