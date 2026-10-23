"use client";

import { useEffect, useRef } from "react";

function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const host = window.location.port === "3000" ? "localhost:8001" : window.location.host;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/playback`;
}

export interface StorageEvent {
  /** `volumes` (branchement, retrait), `library` (disponibilité), `jobs`, `health`, `settings`, `portable`. */
  scope: string;
  /** Nature des changements (`added`, `removed`, `removed_abruptly`, `mounted`, `library_online`…), sans nom ni chemin. */
  changes: string[];
}

/** Changements qui méritent d'avertir l'utilisateur où qu'il soit (branchement et retrait). */
export function isPlugEvent(event: StorageEvent): boolean {
  return event.scope === "volumes" && event.changes.some((c) => c === "added" || c === "removed" || c === "removed_abruptly");
}

/**
 * Écoute les évènements `storage_changed` du serveur (comme `useDevicesEvents`). Ils ne portent AUCUNE donnée :
 * l'appelant relit l'état par REST, derrière le contrôle d'accès (PIN). Reconnexion automatique à attente croissante.
 */
export function useStorageEvents(onChange: (event: StorageEvent) => void, enabled = true): void {
  const callbackRef = useRef(onChange);
  useEffect(() => {
    callbackRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = 1000;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(getWsUrl());
      socket = ws;
      ws.onopen = () => {
        delay = 1000;
        ws.send(JSON.stringify({ command: "subscribe", params: { channels: [] } }));
      };
      ws.onmessage = (message) => {
        try {
          const data = JSON.parse(message.data);
          if (data.event === "ping") ws.send(JSON.stringify({ command: "pong" }));
          else if (data.event === "storage_changed") {
            callbackRef.current({ scope: String(data.scope ?? ""), changes: Array.isArray(data.changes) ? data.changes.map(String) : [] });
          }
        } catch {
          /* message illisible : ignoré */
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [enabled]);
}
