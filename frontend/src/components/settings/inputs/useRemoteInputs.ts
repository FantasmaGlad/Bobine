"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { requestJson } from "@/lib/apiRequest";
import type { RemoteAction, RemoteBindings } from "@/lib/remoteBindings";
import { applyRemoteBindings } from "@/lib/remoteBindingsStore";

export interface RemoteInputs {
  actions: RemoteAction[];
  defaults: RemoteBindings;
  overrides: RemoteBindings;
  bindings: RemoteBindings;
}

export function useRemoteInputs(onError: (message: string) => void) {
  const [inputs, setInputs] = useState<RemoteInputs | null>(null);
  const [failed, setFailed] = useState(false);

  const receive = useCallback((result: Awaited<ReturnType<typeof requestJson<RemoteInputs>>>) => {
    if (result.ok) {
      setInputs(result.data);
      applyRemoteBindings(result.data.bindings);
      return true;
    }
    onError(result.error.message || String(result.error.status));
    return false;
  }, [onError]);

  useEffect(() => {
    let alive = true;
    void requestJson<RemoteInputs>(getApiUrl("/settings/inputs")).then((result) => {
      if (!alive) return;
      if (result.ok) setInputs(result.data);
      else setFailed(true);
    });
    return () => { alive = false; };
  }, []);

  const bind = useCallback(async (input: string, actions: RemoteAction[] | null) =>
    receive(await requestJson<RemoteInputs>(getApiUrl("/settings/inputs"), { method: "PATCH", body: actions === null ? { input } : { input, actions } })), [receive]);
  const reset = useCallback(async () =>
    receive(await requestJson<RemoteInputs>(getApiUrl("/settings/inputs"), { method: "DELETE" })), [receive]);

  return { inputs, failed, bind, reset };
}
