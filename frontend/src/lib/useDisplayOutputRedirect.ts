"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  decideOutputRedirect,
  isLoopbackHost,
  resolveChannel,
  shouldEvaluateRedirect,
  type DisplayChannel,
  type DisplayOutput,
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
  if (typeof window === "undefined") return page === "radio" ? "network" : "cable";
  return resolveChannel(currentSearch(), window.location.hostname, page).channel;
}

export function useDisplayOutputRedirect(
  current: DisplayPage,
  cableOutput: DisplayOutput | null,
  networkOutput: DisplayOutput | null,
) {
  const lastSeenRef = useRef<DisplayOutput | null>(null);
  const router = useRouter();

  useEffect(() => {
    const search = currentSearch();
    const { channel } = resolveChannel(search, window.location.hostname, current);
    if (!shouldEvaluateRedirect(channel, cableOutput, networkOutput, lastSeenRef.current)) return;
    const decision = decideOutputRedirect(
      current,
      search,
      window.location.hostname,
      cableOutput,
      networkOutput,
      lastSeenRef.current,
    );
    lastSeenRef.current = decision.seen;
    if (decision.to) {
      pendingSearch = new URL(decision.to, window.location.origin).search;
      router.replace(decision.to);
    }
  }, [cableOutput, networkOutput, current, router]);
}
