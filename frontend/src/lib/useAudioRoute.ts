"use client";

import { useCallback, useEffect, useRef, type MutableRefObject } from "react";
import { applyRoute, type OutputDevice, type RadioRoute, type RouteStatus, type SinkContext } from "@/lib/audioRoute";
import type { MixStage } from "@/lib/radioMixGraph";

async function listBrowserOutputs(): Promise<OutputDevice[]> {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((d) => d.kind === "audiooutput").map((d) => ({ deviceId: d.deviceId, label: d.label }));
}

interface UseAudioRouteOptions {
  ctxRef: MutableRefObject<AudioContext | null>;
  stageRef: MutableRefObject<MixStage | null>;
  route: RadioRoute | null;
  ready: boolean;
  connected: boolean;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
}

export function useAudioRoute({ ctxRef, stageRef, route, ready, connected, sendCommand }: UseAudioRouteOptions): void {
  const routeRef = useRef(route);
  const sentRef = useRef("");
  const sendRef = useRef(sendCommand);
  useEffect(() => {
    routeRef.current = route;
    sendRef.current = sendCommand;
  });

  const run = useCallback(async () => {
    const ctx = ctxRef.current;
    if (!ctx || !ready) return;
    const current = routeRef.current;
    const status: RouteStatus = await applyRoute(ctx as unknown as SinkContext, current, {
      env: {
        secure: typeof window !== "undefined" && window.isSecureContext,
        canSetSinkId: typeof (ctx as unknown as SinkContext).setSinkId === "function" && !!navigator.mediaDevices?.enumerateDevices,
      },
      listOutputs: listBrowserOutputs,
      setMuted: (muted) => stageRef.current?.setRouteMuted(muted),
    });
    if (!current && !sentRef.current) return;
    if (sentRef.current === status) return;
    sentRef.current = status;
    sendRef.current("radio_report_route", { status });
  }, [ctxRef, stageRef, ready]);

  const routeKey = JSON.stringify(route);
  useEffect(() => {
    void run();
  }, [run, routeKey]);

  useEffect(() => {
    if (!connected) return;
    sentRef.current = "";
    void run();
  }, [connected, run]);

  useEffect(() => {
    const devices = typeof navigator !== "undefined" ? navigator.mediaDevices : undefined;
    if (!devices?.addEventListener) return;
    const onChange = () => void run();
    devices.addEventListener("devicechange", onChange);
    return () => devices.removeEventListener("devicechange", onChange);
  }, [run]);
}
