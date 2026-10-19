"use client";

import { useEffect, useRef } from "react";

function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const host = window.location.port === "3000" ? "localhost:8001" : window.location.host;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/playback`;
}

/**
 * Écoute les évènements `devices_changed` (audio, bluetooth, wifi) du serveur et appelle `onChange(scope)`.
 * L'évènement ne porte AUCUNE donnée : l'appelant relit l'état par REST, derrière le contrôle d'accès (PIN).
 * Connexion légère : abonnement à aucun canal de lecture (seuls les évènements globaux arrivent),
 * reconnexion automatique avec attente croissante, réponse aux ping du serveur.
 */
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
      const ws = new WebSocket(getWsUrl());
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
