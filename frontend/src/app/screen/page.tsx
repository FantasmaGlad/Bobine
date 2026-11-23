"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { getApiUrl } from "@/lib/apiUrl";
import { screenOutput, screenTarget } from "@/lib/displayChannel";

const RETRY_MS = 3000;

export default function ScreenPage() {
  const router = useRouter();

  useEffect(() => {
    const search = window.location.search;
    let cancelled = false;
    let timer: number | undefined;
    const retry = (reason: unknown) => {
      console.warn("Mode de la sortie illisible, nouvel essai", reason);
      if (!cancelled) timer = window.setTimeout(open, RETRY_MS);
    };
    const open = () => {
      fetch(getApiUrl(`/outputs/${screenOutput(search)}`), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
        .then((output: { mode?: unknown }) => {
          const target = screenTarget(search, output.mode);
          if (!target) return retry(output.mode);
          if (!cancelled) router.replace(target);
        })
        .catch(retry);
    };
    open();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [router]);

  return <div aria-busy="true" style={{ position: "fixed", inset: 0, background: "#000" }} />;
}
