"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "./apiUrl.ts";
import { parseDisplayOutput, parseDisplayOutputs, type DisplayOutputs } from "./displayChannel.ts";
import { isOutputId } from "./outputs.ts";
import { useServerEvent, type ServerMessage } from "./useServerEvent.ts";

export function useDisplayOutputs(): DisplayOutputs {
  const [outputs, setOutputs] = useState<DisplayOutputs>({});

  useEffect(() => {
    let cancelled = false;
    fetch(getApiUrl("/outputs"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => {
        if (cancelled) return;
        setOutputs((prev) => parseDisplayOutputs(data, prev));
      })
      .catch((error) => console.warn("Sorties d'écran illisibles", error));
    return () => {
      cancelled = true;
    };
  }, []);

  const onChange = useCallback((message: ServerMessage) => {
    const channel = isOutputId(message.channel) ? message.channel : null;
    const output = channel ? parseDisplayOutput(channel, message.output) : null;
    if (channel && output) setOutputs((prev) => ({ ...prev, [channel]: output }));
  }, []);
  useServerEvent("display_output", onChange);

  return outputs;
}
