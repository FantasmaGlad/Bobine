"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { clearCachesAndReload } from "@/lib/cacheReload";
import type { ClockAnchor } from "@/lib/playbackClock";
import { ServerClockSync } from "@/lib/serverClockSync";
import { parseDisplayOutput, parseDisplayOutputs, type DisplayOutputs } from "@/lib/displayChannel";
import { DEFAULT_RADIO_CHANNEL, isOutputId, type RadioChannelId } from "@/lib/outputs";
import { defaultSound, type RadioSoundSettings } from "@/lib/radioSound";
import { defaultMix, type RadioMix } from "@/lib/radioMix";
import type { RadioRoute } from "@/lib/audioRoute";
import type { ClockTarget } from "@/lib/useMediaClockFollower";
import { getApiUrl, getPlaybackWsUrl } from "@/lib/apiUrl";
import { applyRemoteBindings } from "@/lib/remoteBindingsStore";
import { mergeRadioState, SILENT_LINK_MS, type RadioStatePatch } from "@/lib/radioEvent";

export interface RadioTrackInfo {
  id: number;
  title: string;
  artist: string | null;
  album: string | null;
  genre?: string | null;
  duration_seconds: number | null;
  cover_url: string | null;
}

export type RadioRepeatMode = "off" | "playlist" | "track";

export interface RadioAnnouncementInfo {
  id: number;
  description: string;
  mode: "wait_end" | "duck";
}

export interface RadioState {
  state: "idle" | "playing" | "paused" | "announcing";
  playlist_id: number | null;
  playlist_name: string | null;
  order: RadioTrackInfo[];
  index: number | null;
  current_track: RadioTrackInfo | null;
  position_seconds: number;
  duration_seconds: number | null;
  clock?: ClockAnchor | null;
  volume: number;
  shuffle: boolean;
  repeat: RadioRepeatMode;
  playing: boolean;
  crossfade_seconds: number;
  current_announcement: RadioAnnouncementInfo | null;
  tracks_since_announcement: number;
  sound: RadioSoundSettings;
  mix: RadioMix;
  route: RadioRoute | null;
  meter: boolean;
}

const DEFAULT_STATE: RadioState = {
  state: "idle",
  playlist_id: null,
  playlist_name: null,
  order: [],
  index: null,
  current_track: null,
  position_seconds: 0,
  duration_seconds: null,
  volume: 100,
  shuffle: false,
  repeat: "off",
  playing: false,
  crossfade_seconds: 4,
  current_announcement: null,
  tracks_since_announcement: 0,
  sound: defaultSound(),
  mix: defaultMix(),
  route: null,
  meter: false,
  clock: null,
};

export function selectRadioTarget(state: RadioState): ClockTarget {
  if (!state.current_track || (state.state !== "playing" && state.state !== "paused")) {
    return { anchor: null, mode: null };
  }
  return { anchor: state.clock, mode: state.playing ? "playing" : "paused", key: state.current_track.id };
}

export interface RadioEvent {
  event: "state_change";
  cause: string;
  channel: RadioChannelId;
  data: RadioState;
  client_ts?: number;
}

export function useRadioSocket(
  onEvent?: (evt: RadioEvent) => void,
  role?: "kiosk",
  channel: RadioChannelId = DEFAULT_RADIO_CHANNEL,
) {
  const [state, setState] = useState<RadioState>(DEFAULT_STATE);
  const [connected, setConnected] = useState(false);
  const [isPrimary, setIsPrimary] = useState(false);
  const [displayOutputs, setDisplayOutputs] = useState<DisplayOutputs>({});
  const wsRef = useRef<WebSocket | null>(null);
  const pendingCommandsRef = useRef<{ payload: string; queuedAt: number }[]>([]);
  const onEventRef = useRef(onEvent);
  const stateRef = useRef<RadioState>(DEFAULT_STATE);
  const bootIdRef = useRef<string | null>(null);
  const clockSyncRef = useRef(new ServerClockSync());

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const applyState = useCallback((data: RadioStatePatch, evt: Omit<RadioEvent, "data">) => {
    const next = mergeRadioState(stateRef.current, data);
    stateRef.current = next;
    setState(next);
    onEventRef.current?.({ ...evt, data: next });
  }, []);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let silenceTimer: ReturnType<typeof setTimeout> | undefined;
    let retryDelay = 1000;
    const MAX_RETRY_DELAY = 30000;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(getPlaybackWsUrl([channel]));
      wsRef.current = ws;

      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        setConnected(true);
        retryDelay = 1000;
        ws.send(JSON.stringify({ command: "subscribe", params: { channels: [channel] } }));
        clockSyncRef.current.start(ws, () => wsRef.current === ws);
        if (role === "kiosk") {
          ws.send(JSON.stringify({ command: "identify", params: { role: "kiosk", channel } }));
        }
        const now = Date.now();
        const pending = pendingCommandsRef.current.filter((p) => now - p.queuedAt < 5000);
        pendingCommandsRef.current = [];
        for (const p of pending) ws.send(p.payload);
      };

      ws.onmessage = (evt) => {
        if (wsRef.current !== ws) return;
        clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => ws.close(), SILENT_LINK_MS);
        try {
          const parsed = JSON.parse(evt.data);
          if (parsed.event === "ping") {
            ws.send(JSON.stringify({ command: "pong" }));
            return;
          }
          if (clockSyncRef.current.handleMessage(parsed)) return;
          if (parsed.event === "boot_id") {
            if (bootIdRef.current === null) {
              bootIdRef.current = parsed.boot_id;
            } else if (bootIdRef.current !== parsed.boot_id) {
              void clearCachesAndReload();
            }
            return;
          }
          if (parsed.event === "kiosk_role") {
            setIsPrimary(!!parsed.is_primary);
            return;
          }
          if (parsed.event === "promoted_primary") {
            setIsPrimary(true);
            return;
          }
          if (parsed.event === "display_output") {
            const screen = isOutputId(parsed.channel) ? parsed.channel : null;
            const output = screen ? parseDisplayOutput(screen, parsed.output) : null;
            if (screen && output) setDisplayOutputs((prev) => ({ ...prev, [screen]: output }));
            return;
          }
          if (parsed.event === "inputs_change") {
            applyRemoteBindings(parsed.bindings);
            return;
          }
          if (parsed.event === "force_reload") {
            void clearCachesAndReload();
            return;
          }
          if (parsed.event === "state_change" && parsed.channel === channel) {
            applyState(parsed.data, parsed);
          }
        } catch (err) {
          console.error("Message WebSocket radio invalide", err);
        }
      };

      ws.onclose = () => {
        clearTimeout(silenceTimer);
        clockSyncRef.current.stop();
        if (wsRef.current !== ws) return;
        setConnected(false);
        setIsPrimary(false);
        wsRef.current = null;
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      clearTimeout(silenceTimer);
      wsRef.current?.close();
    };
  }, [role, channel, applyState]);

  useEffect(() => {
    let cancelled = false;
    const resync = () => {
      if (document.visibilityState !== "visible") return;
      fetch(getApiUrl(`/radio/state?channel=${channel}`), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data: RadioState | null) => {
          if (!cancelled && data) applyState(data, { event: "state_change", cause: "sync", channel });
        })
        .catch((err) => console.warn("Relecture de l'état radio impossible", err));
    };
    document.addEventListener("visibilitychange", resync);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", resync);
    };
  }, [channel, applyState]);

  useEffect(() => {
    let cancelled = false;
    fetch(getApiUrl("/settings/display-output"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setDisplayOutputs((prev) => parseDisplayOutputs(data, prev));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const sendCommand = useCallback((command: string, params: Record<string, unknown> = {}) => {
    const ws = wsRef.current;
    const payload = JSON.stringify({
      command,
      params: { channel, ...params, client_ts: Date.now() },
    });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
      return;
    }
    pendingCommandsRef.current.push({ payload, queuedAt: Date.now() });
    if (pendingCommandsRef.current.length > 10) pendingCommandsRef.current.shift();
  }, [channel]);

  const serverNow = useCallback(() => clockSyncRef.current.serverNow(), []);

  return { state, connected, sendCommand, isPrimary, serverNow, displayOutputs };
}
