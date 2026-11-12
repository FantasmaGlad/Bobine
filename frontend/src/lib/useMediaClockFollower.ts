"use client";

import { useEffect, useRef } from "react";
import { anchorPosition, msUntilStart, planDrift, type ClockAnchor } from "@/lib/playbackClock";

const FOLLOW_INTERVAL_MS = 200;
const HOLD_SEEK_THRESHOLD_S = 0.25;
const LATE_START_SEEK_THRESHOLD_S = 1.0;
const SETTLE_AFTER_SEEK_MS = 1500;
const MIN_MS_BETWEEN_SEEKS = 4000;
const SEEK_LATENCY_COMPENSATION_S = 0.2;
const START_ARM_WINDOW_MS = 600;

export interface ClockTarget {
  anchor: ClockAnchor | null | undefined;
  mode: "playing" | "paused" | null;
  key?: string | number | null;
}

interface Options<S> {
  mediaRef: { current: HTMLMediaElement | null };
  state: S;
  select: (state: S) => ClockTarget;
  enabled?: boolean;
  isMediaForKey?: (el: HTMLMediaElement, key: string | number | null | undefined) => boolean;
  serverNow: () => number;
  tryPlay: (el: HTMLMediaElement | null | undefined) => void;
  onSeek?: () => void;
}

export function useMediaClockFollower<S>({ mediaRef, state, select, enabled = true, isMediaForKey, serverNow, tryPlay, onSeek }: Options<S>) {
  const stateRef = useRef(state);
  const selectRef = useRef(select);
  const enabledRef = useRef(enabled);
  const isMediaForKeyRef = useRef(isMediaForKey);
  const serverNowRef = useRef(serverNow);
  const tryPlayRef = useRef(tryPlay);
  const onSeekRef = useRef(onSeek);
  useEffect(() => {
    stateRef.current = state;
    selectRef.current = select;
    enabledRef.current = enabled;
    isMediaForKeyRef.current = isMediaForKey;
    serverNowRef.current = serverNow;
    tryPlayRef.current = tryPlay;
    onSeekRef.current = onSeek;
  });

  const tickRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let correcting = false;
    let lastSeekAt = 0;
    let handledEpoch: number | undefined;
    let lastPlayAttemptAt = 0;
    let startTimer: ReturnType<typeof setTimeout> | null = null;

    const playThrottled = (video: HTMLMediaElement) => {
      if (Date.now() - lastPlayAttemptAt < 1000) return;
      lastPlayAttemptAt = Date.now();
      tryPlayRef.current(video);
    };

    const seekSafely = (video: HTMLMediaElement, position: number, resume: boolean) => {
      lastSeekAt = Date.now();
      onSeekRef.current?.();
      const wasPlaying = !video.paused;
      if (wasPlaying) video.pause();
      try {
        video.currentTime = Math.max(0, position);
      } catch {
        return;
      }
      if (resume && wasPlaying) {
        const onSeeked = () => {
          video.removeEventListener("seeked", onSeeked);
          tryPlayRef.current(video);
        };
        video.addEventListener("seeked", onSeeked, { once: true });
        setTimeout(() => {
          video.removeEventListener("seeked", onSeeked);
          if (video.paused && selectRef.current(stateRef.current).mode === "playing") tryPlayRef.current(video);
        }, 1500);
      }
    };

    const tick = () => {
      if (!enabledRef.current) return;
      const video = mediaRef.current;
      const target0 = selectRef.current(stateRef.current);
      const anchor = target0.anchor;
      if (!video || !video.src || !anchor || target0.mode === null) return;
      if (video.ended) return;
      if (isMediaForKeyRef.current && !isMediaForKeyRef.current(video, target0.key)) return;
      if (video.readyState < HTMLMediaElement.HAVE_METADATA) return;

      const now = serverNowRef.current();
      const target = anchorPosition(anchor, now);
      const nominal = anchor.rate;

      if (video.seeking) return;

      if (target0.mode === "paused" || !anchor.running) {
        if (!video.paused) video.pause();
        if (video.playbackRate !== nominal) video.playbackRate = nominal;
        correcting = false;
        if (Math.abs(video.currentTime - target) > HOLD_SEEK_THRESHOLD_S) {
          seekSafely(video, target, false);
        }
        return;
      }

      const wait = msUntilStart(anchor, now);
      if (wait > 0) {
        if (!video.paused) video.pause();
        if (Math.abs(video.currentTime - anchor.pos) > HOLD_SEEK_THRESHOLD_S) {
          seekSafely(video, anchor.pos, false);
          return;
        }
        if (wait <= START_ARM_WINDOW_MS && startTimer === null) {
          startTimer = setTimeout(() => {
            startTimer = null;
            const v = mediaRef.current;
            if (v && v.paused && selectRef.current(stateRef.current).mode === "playing") tryPlayRef.current(v);
          }, wait);
        }
        return;
      }

      if (video.paused) {
        if (Math.abs(video.currentTime - target) > LATE_START_SEEK_THRESHOLD_S) {
          seekSafely(video, target + SEEK_LATENCY_COMPENSATION_S, true);
        }
        playThrottled(video);
        return;
      }
      if (video.readyState < HTMLMediaElement.HAVE_FUTURE_DATA) return;
      const explicit = anchor.epoch !== undefined && anchor.epoch !== handledEpoch;
      if (anchor.epoch !== undefined) handledEpoch = anchor.epoch;
      if (!explicit && Date.now() - lastSeekAt < SETTLE_AFTER_SEEK_MS) return;

      const plan = planDrift(video.currentTime - target, nominal, correcting, explicit);
      if (plan.action === "seek") {
        if (explicit || Date.now() - lastSeekAt >= MIN_MS_BETWEEN_SEEKS) {
          correcting = false;
          video.playbackRate = nominal;
          seekSafely(video, target + SEEK_LATENCY_COMPENSATION_S, true);
        }
        return;
      }
      correcting = plan.action === "rate";
      if (Math.abs(video.playbackRate - plan.playbackRate) > 0.001) {
        video.playbackRate = plan.playbackRate;
      }
    };

    tickRef.current = tick;
    const id = setInterval(tick, FOLLOW_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      tickRef.current = null;
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
      if (startTimer) clearTimeout(startTimer);
    };
  }, [mediaRef]);

  const current = select(state);
  const anchor = current.anchor;
  useEffect(() => {
    tickRef.current?.();
  }, [anchor?.at_ms, anchor?.running, anchor?.pos, anchor?.rate, anchor?.epoch, current.mode, current.key, enabled]);
}
