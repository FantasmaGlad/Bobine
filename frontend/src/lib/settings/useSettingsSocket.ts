import { useEffect } from "react";
import { getPlaybackWsUrl } from "@/lib/apiUrl";
import { clearCachesAndReload } from "@/lib/cacheReload";
import { readLook, type SettingsPatch } from "./payload";
import type { WiredDisplayMode } from "./types";

interface SettingsSocketHandlers {
  apply: (patch: SettingsPatch) => void;
  refetch: () => void;
}

function handleMessage(ws: WebSocket, parsed: Record<string, unknown>, boot: { id: string | null }, handlers: SettingsSocketHandlers) {
  if (parsed.event === "ping") {
    ws.send(JSON.stringify({ command: "pong" }));
    return;
  }
  if (parsed.event === "boot_id") {
    if (boot.id === null) boot.id = parsed.boot_id as string;
    else if (boot.id !== parsed.boot_id) void clearCachesAndReload();
    return;
  }
  if (parsed.event === "settings_change") handlers.apply(readLook(parsed));
  if (parsed.event === "display_mode_change") {
    const mode = parsed.mode || parsed.wired_display_mode;
    if (mode === "dual_screen" || mode === "headless") handlers.apply({ wiredDisplayMode: mode as WiredDisplayMode });
    handlers.refetch();
  }
}

export function useSettingsSocket(handlers: SettingsSocketHandlers) {
  const { apply, refetch } = handlers;
  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    const boot = { id: null as string | null };

    const connect = () => {
      if (cancelled || typeof window === "undefined") return;
      const socket = new WebSocket(getPlaybackWsUrl());
      ws = socket;
      socket.onopen = () => socket.send(JSON.stringify({ command: "subscribe", params: { channels: [] } }));
      socket.onmessage = (evt) => {
        try {
          handleMessage(socket, JSON.parse(evt.data), boot, { apply, refetch });
        } catch {
        }
      };
      socket.onclose = () => {
        if (!cancelled) reconnectTimer = setTimeout(connect, 3000);
      };
      socket.onerror = () => socket.close();
    };

    connect();
    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [apply, refetch]);
}
