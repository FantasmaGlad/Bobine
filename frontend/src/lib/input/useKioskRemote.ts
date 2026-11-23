"use client";

import { useEffect, useRef } from "react";
import { loadRemoteBindings } from "../remoteBindingsStore.ts";
import { actionHandlers, type RemoteHandlers } from "./dispatch.ts";
import { listenGamepads } from "./gamepad.ts";
import { listenKeyboard } from "./keyboard.ts";

export function useKioskRemote(getHandlers: () => RemoteHandlers, enabled = true) {
  const handlersRef = useRef(getHandlers);
  useEffect(() => {
    handlersRef.current = getHandlers;
  });

  useEffect(() => {
    if (!enabled) return;
    void loadRemoteBindings();
    const handlers = () => actionHandlers(handlersRef.current());
    const stopKeyboard = listenKeyboard(handlers);
    const stopGamepads = listenGamepads(handlers);
    return () => {
      stopKeyboard();
      stopGamepads();
    };
  }, [enabled]);
}
