"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { clearCachesAndReload } from "@/lib/cacheReload";
import { createPageClientId, type DisplayOutput } from "@/lib/displayChannel";
import { type ClockAnchor } from "@/lib/playbackClock";
import type { RadioSoundSettings } from "@/lib/radioSound";
import { ServerClockSync } from "@/lib/serverClockSync";
import { getApiUrl, getPlaybackWsUrl } from "@/lib/apiUrl";

export type PlaybackStateValue =
  | "waiting"
  | "playing"
  | "paused"
  | "coach_mode"
  | "offline"
  | "playlist_waiting"
  | "background";

export interface PlaybackVideo {
  id: number;
  title: string;
  duration_seconds: number | null;
  program?: string | null;
  release?: string | null;
  thumbnail_url?: string | null;
  thumbnail_path?: string | null;
  description?: string | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
  fps?: number | null;
  bitrate_kbps?: number | null;
  width?: number | null;
  height?: number | null;
}

export interface PlaybackBackground {
  id: number;
  title: string;
  is_image?: boolean;
}

export type AudioChainMode = "auto" | "timer" | "manual";

export interface PlaybackAudioCourse {
  id: number;
  title: string;
  program: string | null;
  background_id: number | null;
}

export interface PlaybackAudioTrack {
  id: number;
  number: number | null;
  title: string;
  duration_seconds: number | null;
  background_id?: number | null;
  background_title?: string | null;
  background_is_image?: boolean;
}

export interface PlaybackState {
  state: PlaybackStateValue;
  current_video: PlaybackVideo | null;
  subtitle?: number | "off" | null;
  position_seconds: number;
  volume: number;
  sound?: RadioSoundSettings;
  speed: number;
  playlist_id: number | null;
  playlist_name: string | null;
  playlist_items: PlaybackVideo[] | null;
  playlist_index: number | null;
  playlist_waiting_remaining: number | null;
  current_background: PlaybackBackground | null;
  current_audio_course: PlaybackAudioCourse | null;
  audio_tracks: PlaybackAudioTrack[] | null;
  audio_track_index: number | null;
  audio_playing: boolean;
  audio_position_seconds: number;
  audio_chain_mode: AudioChainMode;
  audio_chain_timer_seconds: number;
  audio_chain_wait_remaining: number | null;
  clock?: ClockAnchor | null;
  audio_clock?: ClockAnchor | null;
}

export type PlaybackChannel = "cable" | "network";

export interface CinemaRemoteState {
  title: string | null;
  program: string | null;
  position_seconds: number;
  duration_seconds: number;
  playing: boolean;
  video_id?: number | null;
  reported_at: number;
}

export interface CinemaCommandExtra {
  title?: string;
  duration_seconds?: number | null;
  clock?: ClockAnchor;
  clock_video_id?: number;
}

export type CinemaCommandAction = "play" | "pause" | "seek" | "stop" | "launch";

export interface PlaybackEvent {
  event: "state_change" | "position_tick";
  cause: string;
  client_ts?: number;
  channel?: PlaybackChannel;
  data: PlaybackState;
  tick_seq?: number;
}

const DEFAULT_STATE: PlaybackState = {
  state: "waiting",
  current_video: null,
  position_seconds: 0,
  volume: 100,
  speed: 1.0,
  playlist_id: null,
  playlist_name: null,
  playlist_items: null,
  playlist_index: null,
  playlist_waiting_remaining: null,
  current_background: null,
  current_audio_course: null,
  audio_tracks: null,
  audio_track_index: null,
  audio_playing: false,
  audio_position_seconds: 0,
  audio_chain_mode: "auto",
  audio_chain_timer_seconds: 20,
  audio_chain_wait_remaining: null,
  clock: null,
  audio_clock: null,
};

const RESYNC_INTERVAL_MS = 15000;

let pageClientId: string | null = null;

function getPageKioskClientId(): string {
  if (typeof window === "undefined") return "";
  if (pageClientId === null) pageClientId = createPageClientId();
  return pageClientId;
}

export function usePlaybackSocket(
  onEvent?: (evt: PlaybackEvent) => void,
  role?: "kiosk",
  channel: PlaybackChannel = "cable",
  onCinemaCommand?: (action: CinemaCommandAction, positionSeconds: number, videoId?: number, extra?: CinemaCommandExtra) => void,
  page?: string,
) {
  const [state, setState] = useState<PlaybackState>(DEFAULT_STATE);
  const [connected, setConnected] = useState(false);
  const [cinemaState, setCinemaState] = useState<CinemaRemoteState | null>(null);
  const [displayOutputCable, setDisplayOutputCable] = useState<DisplayOutput | null>(null);
  const [displayOutputNetwork, setDisplayOutputNetwork] = useState<"kiosk" | "cinema" | null>(null);
  const [cinemaLocked, setCinemaLocked] = useState(false);
  const [lockedReason, setLockedReason] = useState<"cinema" | "radio" | null>(null);
  const cinemaLockedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isPrimary, setIsPrimary] = useState(false);
  const [libraryVersion, setLibraryVersion] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const lastMessageAtRef = useRef(Date.now());
  const pendingCommandsRef = useRef<{ payload: string; queuedAt: number }[]>([]);
  const bootIdRef = useRef<string | null>(null);
  const lastTickSeqRef = useRef<number | null>(null);
  const clockSyncRef = useRef(new ServerClockSync());
  const doResyncRef = useRef<() => void>(() => {});
  const onEventRef = useRef(onEvent);
  const onCinemaCommandRef = useRef(onCinemaCommand);
  const stateRef = useRef<PlaybackState>(DEFAULT_STATE);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    onCinemaCommandRef.current = onCinemaCommand;
  }, [onCinemaCommand]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let retryDelay = 1000;
    const MAX_RETRY_DELAY = 30000;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(getPlaybackWsUrl());
      wsRef.current = ws;

      const sendIdentify = () => {
        if (wsRef.current !== ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({
          command: "identify",
          params: { role: "kiosk", channel, client_id: getPageKioskClientId(), ...(page ? { page } : {}) },
        }));
      };

      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        setConnected(true);
        retryDelay = 1000;
        lastMessageAtRef.current = Date.now();
        lastTickSeqRef.current = null;
        clockSyncRef.current.start(ws, () => wsRef.current === ws);
        ws.send(JSON.stringify({ command: "subscribe", params: { channels: [channel] } }));
        if (role === "kiosk") {
          sendIdentify();
        } else if (page) {
          ws.send(JSON.stringify({ command: "identify", params: { role: "viewer", channel, page } }));
        }
        const now = Date.now();
        const pending = pendingCommandsRef.current.filter((p) => now - p.queuedAt < 5000);
        pendingCommandsRef.current = [];
        for (const p of pending) ws.send(p.payload);
      };

      ws.onmessage = (evt) => {
        if (wsRef.current !== ws) return;
        lastMessageAtRef.current = Date.now();
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
            sendIdentify();
            return;
          }
          if (parsed.event === "display_output") {
            if (parsed.channel === "cable" && (parsed.output === "kiosk" || parsed.output === "cinema" || parsed.output === "radio")) {
              setDisplayOutputCable(parsed.output);
            } else if (parsed.channel === "network" && (parsed.output === "kiosk" || parsed.output === "cinema")) {
              setDisplayOutputNetwork(parsed.output);
            }
            return;
          }
          if (parsed.event === "command_rejected") {
            if (parsed.reason === "cinema_locked" || parsed.reason === "radio_locked") {
              setLockedReason(parsed.reason === "radio_locked" ? "radio" : "cinema");
              setCinemaLocked(true);
              if (cinemaLockedTimerRef.current) clearTimeout(cinemaLockedTimerRef.current);
              cinemaLockedTimerRef.current = setTimeout(() => setCinemaLocked(false), 5000);
            }
            return;
          }
          if (parsed.event === "cinema_state") {
            if ((parsed.channel ?? "cable") !== channel) return;
            setCinemaState(parsed.data ?? null);
            return;
          }
          if (parsed.event === "cinema_command") {
            if ((parsed.channel ?? "cable") !== channel) return;
            onCinemaCommandRef.current?.(
              parsed.action,
              parsed.position_seconds ?? 0,
              parsed.video_id ?? undefined,
              { title: parsed.title, duration_seconds: parsed.duration_seconds, clock: parsed.clock, clock_video_id: parsed.clock_video_id }
            );
            return;
          }
          if (parsed.event === "library_change") {
            setLibraryVersion((v) => v + 1);
            return;
          }
          if (parsed.event === "force_reload") {
            void clearCachesAndReload();
            return;
          }
          if (parsed.event === "state_change" || parsed.event === "position_tick") {
            if ((parsed.channel ?? "cable") !== channel) return;
            if (parsed.cause === "position_tick" && typeof parsed.tick_seq === "number") {
              const previous = lastTickSeqRef.current;
              if (previous !== null && parsed.tick_seq > previous + 1) {
                doResyncRef.current();
              }
              lastTickSeqRef.current = parsed.tick_seq;
            }
            setState(parsed.data);
            onEventRef.current?.(parsed as PlaybackEvent);
          }
        } catch (err) {
          console.error("Message WebSocket playback invalide", err);
        }
      };

      ws.onclose = () => {
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

    const onVisible = () => {
      if (typeof document === "undefined" || document.visibilityState !== "visible") return;
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: "pong" }));
      }
    };
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", onVisible);
    }

    const STALE_THRESHOLD_ACTIVE_MS = 5000;
    const STALE_THRESHOLD_IDLE_MS = 35000;
    const staleWatchdog = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      const current = wsRef.current;
      if (!current || current.readyState !== WebSocket.OPEN) return;
      const isActivelyPlaying =
        stateRef.current.state === "playing" || stateRef.current.audio_playing;
      const threshold = isActivelyPlaying ? STALE_THRESHOLD_ACTIVE_MS : STALE_THRESHOLD_IDLE_MS;
      if (Date.now() - lastMessageAtRef.current > threshold) {
        current.close();
      }
    }, 2000);

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      clearInterval(staleWatchdog);
      if (cinemaLockedTimerRef.current) clearTimeout(cinemaLockedTimerRef.current);
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisible);
      }
      wsRef.current?.close();
    };
  }, [role, channel]);

  useEffect(() => {
    let cancelled = false;
    const resync = () => {
      if (cancelled) return;
      fetch(getApiUrl(`/playback/state?channel=${channel}`), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data: PlaybackState | null) => {
          if (cancelled || !data) return;
          if (JSON.stringify(stateRef.current) === JSON.stringify(data)) return;
          setState(data);
          onEventRef.current?.({ event: "state_change", cause: "sync", data });
        })
        .catch(() => {
        });
    };
    doResyncRef.current = resync;
    const id = setInterval(resync, RESYNC_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
      doResyncRef.current = () => {};
    };
  }, [channel]);

  useEffect(() => {
    let cancelled = false;
    fetch(getApiUrl("/settings/display-output"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        if (data.cable === "kiosk" || data.cable === "cinema" || data.cable === "radio") {
          setDisplayOutputCable((prev) => prev ?? data.cable);
        }
        if (data.network === "kiosk" || data.network === "cinema") {
          setDisplayOutputNetwork((prev) => prev ?? data.network);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const serverNow = useCallback(() => clockSyncRef.current.serverNow(), []);

  const sendCommand = useCallback((command: string, params: Record<string, unknown> = {}) => {
    const ws = wsRef.current;
    const payload = JSON.stringify({ command, params: { channel, ...params, client_ts: Date.now() } });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
      return;
    }
    pendingCommandsRef.current.push({ payload, queuedAt: Date.now() });
    if (pendingCommandsRef.current.length > 10) pendingCommandsRef.current.shift();
  }, [channel]);

  return {
    state, connected, sendCommand, serverNow, isPrimary, displayOutputCable, displayOutputNetwork,
    cinemaLocked, lockedReason, cinemaState, libraryVersion,
  };
}

