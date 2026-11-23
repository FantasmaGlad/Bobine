"use client";

import { useEffect, useRef } from "react";
import { getPlaybackWsUrl } from "./apiUrl.ts";

export type ServerMessage = Record<string, unknown>;

export function useServerEvent(event: string, onMessage: (message: ServerMessage) => void, enabled = true): void {
  const callbackRef = useRef(onMessage);
  useEffect(() => {
    callbackRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = 1000;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(getPlaybackWsUrl([]));
      socket = ws;
      ws.onopen = () => {
        delay = 1000;
        ws.send(JSON.stringify({ command: "subscribe", params: { channels: [] } }));
      };
      ws.onmessage = (message) => {
        try {
          const data = JSON.parse(message.data);
          if (data.event === "ping") ws.send(JSON.stringify({ command: "pong" }));
          else if (data.event === event) callbackRef.current(data);
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
  }, [event, enabled]);
}
