"use client";

import { useEffect, useRef } from "react";
import { getPlaybackWsUrl } from "./apiUrl.ts";

export function useDevicesEvents(onChange: (scope: string) => void, enabled = true): void {
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
      const ws = new WebSocket(getPlaybackWsUrl());
      socket = ws;
      ws.onopen = () => {
        delay = 1000;
        ws.send(JSON.stringify({ command: "subscribe", params: { channels: [] } }));
      };
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.event === "ping") ws.send(JSON.stringify({ command: "pong" }));
          else if (message.event === "devices_changed") callbackRef.current(String(message.scope ?? ""));
        } catch {
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
