"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { DEFAULT_OUTPUT, DEFAULT_RADIO_CHANNEL, outputOfRadio } from "@/lib/outputs";
import {
  decideOutputRedirect,
  isLoopbackHost,
  resolveChannel,
  shouldEvaluateRedirect,
  type DisplayChannel,
  type DisplayOutput,
  type DisplayOutputs,
  type DisplayPage,
} from "@/lib/displayChannel";

export function isWiredDisplay(): boolean {
  if (typeof window === "undefined") return false;
  return isLoopbackHost(window.location.hostname);
}

let pendingSearch: string | null = null;

function currentSearch(): string {
  if (pendingSearch !== null && pendingSearch !== window.location.search) return pendingSearch;
  pendingSearch = null;
  return window.location.search;
}

export function getDisplayChannel(page: DisplayPage): DisplayChannel {
  if (typeof window === "undefined") return page === "radio" ? outputOfRadio(DEFAULT_RADIO_CHANNEL).id : DEFAULT_OUTPUT;
  return resolveChannel(currentSearch(), window.location.hostname, page).channel;
}

export function useDisplayOutputRedirect(
  current: DisplayPage,
  outputs: DisplayOutputs,
) {
  const lastSeenRef = useRef<DisplayOutput | null>(null);
  const router = useRouter();

  useEffect(() => {
    const search = currentSearch();
    const { channel } = resolveChannel(search, window.location.hostname, current);
    if (!shouldEvaluateRedirect(channel, outputs, lastSeenRef.current)) return;
    const decision = decideOutputRedirect(
      current,
      search,
      window.location.hostname,
      outputs,
      lastSeenRef.current,
    );
    lastSeenRef.current = decision.seen;
    if (decision.to) {
      pendingSearch = new URL(decision.to, window.location.origin).search;
      router.replace(decision.to);
    }
  }, [outputs, current, router]);
}
