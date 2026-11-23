"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { entryDurationMs, nextIndex, streamPath, type SignageEntry } from "@/lib/signageLoop";

function Slide({ entry, loop, onEnded }: { entry: SignageEntry; loop: boolean; onEnded: () => void }) {
  const src = getApiUrl(streamPath(entry.background_id));
  return (
    <div className="signage-slide">
      {entry.is_image
        ? <img src={src} alt={entry.title} />
        : <video src={src} autoPlay muted playsInline loop={loop} onEnded={onEnded} />}
    </div>
  );
}

export default function SignagePlayer({ entries, emptyLabel }: { entries: SignageEntry[]; emptyLabel: string }) {
  const [turn, setTurn] = useState({ index: 0, count: 0 });
  const at = entries.length === 0 ? 0 : turn.index % entries.length;
  const current = entries[at];
  const alone = entries.length === 1;
  const advance = useCallback(
    () => setTurn((t) => ({ index: nextIndex(t.index % Math.max(entries.length, 1), entries.length), count: t.count + 1 })),
    [entries.length],
  );

  useEffect(() => {
    if (!current || (alone && current.is_image)) return;
    const duration = entryDurationMs(current);
    if (duration === null) return;
    const timer = window.setTimeout(advance, duration);
    return () => window.clearTimeout(timer);
  }, [current, alone, advance, turn.count]);

  if (!current) return <div className="signage-screen signage-empty">{emptyLabel}</div>;
  return (
    <div className="signage-screen">
      <Slide key={`${turn.count}-${current.background_id}`} entry={current} loop={alone && current.play_seconds === null} onEnded={advance} />
    </div>
  );
}
