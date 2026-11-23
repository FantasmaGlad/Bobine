"use client";

import { useEffect, useMemo, useRef } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { streamPath, type SignageEntry } from "@/lib/signageLoop";
import { Compositor } from "./engine/compositor";
import { SignageEngine } from "./engine/engine";
import { prepareSlide } from "./engine/prepare";

const prepare = (entry: SignageEntry, loop: boolean) => prepareSlide(entry, getApiUrl(streamPath(entry.visual_id)), loop);

export default function SignagePlayer({ entries, emptyLabel }: { entries: SignageEntry[]; emptyLabel: string }) {
  const first = useRef<HTMLDivElement>(null);
  const second = useRef<HTMLDivElement>(null);
  const engine = useRef<SignageEngine | null>(null);
  const key = useMemo(() => JSON.stringify(entries), [entries]);

  useEffect(() => {
    if (!first.current || !second.current) return;
    const created = new SignageEngine(new Compositor([first.current, second.current]), prepare);
    engine.current = created;
    return () => {
      created.stop();
      engine.current = null;
    };
  }, []);

  useEffect(() => {
    engine.current?.load(JSON.parse(key) as SignageEntry[]);
  }, [key]);

  return (
    <div className="signage-screen">
      <div ref={first} className="signage-layer" />
      <div ref={second} className="signage-layer" />
      {entries.length === 0 && <div className="signage-empty">{emptyLabel}</div>}
    </div>
  );
}
