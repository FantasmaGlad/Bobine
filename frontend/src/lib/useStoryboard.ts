"use client";

import { useEffect, useState } from "react";
import { getApiUrl } from "./apiUrl.ts";
import type { Storyboard } from "./storyboard.ts";

export function useStoryboard(videoId: number | null | undefined): Storyboard | null {
  const [loaded, setLoaded] = useState<{ id: number; board: Storyboard | null } | null>(null);
  useEffect(() => {
    if (!videoId) return;
    let cancelled = false;
    fetch(getApiUrl(`/videos/${videoId}/storyboard`), { cache: "no-store" })
      .then((res) => (res.ok ? (res.json() as Promise<Storyboard>) : null))
      .then((board) => { if (!cancelled) setLoaded({ id: videoId, board: board ? { ...board, url: getApiUrl(board.url.replace(/^\/api/, "")) } : null }); })
      .catch(() => { if (!cancelled) setLoaded({ id: videoId, board: null }); });
    return () => { cancelled = true; };
  }, [videoId]);
  return videoId && loaded?.id === videoId ? loaded.board : null;
}
