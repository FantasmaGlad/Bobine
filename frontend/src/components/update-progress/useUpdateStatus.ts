import { useCallback, useEffect, useState } from "react";
import { getApiUrl, getPlaybackWsUrl } from "@/lib/apiUrl";
import { type UpdateStatus } from "./updateStatus";

function subscribeUpdateProgress(apply: (status: UpdateStatus) => void): () => void {
  let cancelled = false;
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout>;

  const connect = () => {
    if (cancelled || typeof window === "undefined") return;
    ws = new WebSocket(getPlaybackWsUrl([]));
    ws.onopen = () => ws?.send(JSON.stringify({ command: "subscribe", params: { channels: [] } }));
    ws.onmessage = (evt) => {
      try {
        const parsed = JSON.parse(evt.data);
        if (parsed.event === "ping") {
          ws?.send(JSON.stringify({ command: "pong" }));
          return;
        }
        if (parsed.event === "update_progress") apply(parsed as UpdateStatus);
      } catch {
      }
    };
    ws.onclose = () => {
      if (!cancelled) reconnectTimer = setTimeout(connect, 3000);
    };
    ws.onerror = () => ws?.close();
  };

  connect();
  return () => {
    cancelled = true;
    clearTimeout(reconnectTimer);
    ws?.close();
  };
}

export function useUpdateStatus() {
  const [status, setStatus] = useState<UpdateStatus | null>(null);

  const applyStatus = useCallback((data: UpdateStatus | null | undefined) => {
    if (!data || !data.step) return;
    setStatus(data);
  }, []);

  const acknowledge = useCallback(() => {
    setStatus((prev) => (prev ? { ...prev, acknowledged_started_at: prev.started_at } : prev));
    fetch(getApiUrl("/updates/acknowledge"), { method: "POST" }).catch(() => {});
  }, []);

  useEffect(() => {
    fetch(getApiUrl("/updates/status"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then(applyStatus)
      .catch(() => {});
  }, [applyStatus]);

  useEffect(() => subscribeUpdateProgress(applyStatus), [applyStatus]);

  return { status, acknowledge };
}
