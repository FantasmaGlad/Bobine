"use client";

import React, { useEffect, useRef } from "react";

import type { CinemaVideo } from "@/lib/cinemaCatalog";

type MediaRef = React.RefObject<HTMLVideoElement | null>;
type Send = (type: string, payload: Record<string, unknown>) => void;

export function useStallWatchdog(videoRef: MediaRef, lastSeekRef: React.RefObject<number>) {
  useEffect(() => {
    let lastTime = -1;
    let stalls = 0;
    const id = window.setInterval(() => {
      const video = videoRef.current;
      if (!video || video.paused || video.seeking || video.ended || !video.src) {
        lastTime = -1;
        stalls = 0;
        return;
      }
      if (Date.now() - lastSeekRef.current < 3500) {
        lastTime = video.currentTime;
        stalls = 0;
        return;
      }
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        stalls = Math.abs(video.currentTime - lastTime) < 0.05 ? stalls + 1 : 0;
        if (stalls >= 3) {
          stalls = 0;
          video.play().catch(() => {});
        }
      }
      lastTime = video.currentTime;
    }, 2500);
    return () => window.clearInterval(id);
  }, [videoRef, lastSeekRef]);
}

export function useCinemaReport(playing: boolean, selected: CinemaVideo | null, videoRef: MediaRef, sendCommand: Send) {
  const reportNow = useRef<(() => void) | null>(null);
  useEffect(() => {
    if (!playing) {
      reportNow.current = null;
      sendCommand("cinema_report", { title: null, playing: false, position_seconds: 0, duration_seconds: 0 });
      return;
    }
    const report = () => {
      const el = videoRef.current;
      if (el?.seeking) return;
      sendCommand("cinema_report", {
        title: selected?.title ?? null,
        video_id: selected?.id ?? null,
        program: selected?.program ?? null,
        position_seconds: el?.currentTime ?? 0,
        duration_seconds: selected?.duration_seconds ?? el?.duration ?? 0,
        playing: el ? !el.paused : false,
      });
    };
    reportNow.current = report;
    report();
    const id = setInterval(report, 2000);
    return () => {
      reportNow.current = null;
      clearInterval(id);
    };
  }, [playing, selected, videoRef, sendCommand]);
  return reportNow;
}
