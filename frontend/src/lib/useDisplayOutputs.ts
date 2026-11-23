"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "./apiUrl.ts";
import { parseDisplayOutput, type DisplayOutput } from "./displayChannel.ts";
import { isOutputId } from "./outputs.ts";
import { useServerEvent, type ServerMessage } from "./useServerEvent.ts";

export interface DisplayOutputs {
  cable: DisplayOutput | null;
  network: DisplayOutput | null;
}

export function useDisplayOutputs(): DisplayOutputs {
  const [outputs, setOutputs] = useState<DisplayOutputs>({ cable: null, network: null });

  useEffect(() => {
    let cancelled = false;
    fetch(getApiUrl("/settings/display-output"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => {
        if (cancelled) return;
        setOutputs((prev) => ({
          cable: prev.cable ?? parseDisplayOutput("cable", data.cable),
          network: prev.network ?? parseDisplayOutput("network", data.network),
        }));
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
