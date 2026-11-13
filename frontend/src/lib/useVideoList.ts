import { useEffect, useState } from "react";

const EMPTY: never[] = [];

export function useVideoList<T>(videoId: number | null | undefined, getApiUrl: (path: string) => string, resource: string): T[] {
  const [loaded, setLoaded] = useState<{ id: number; items: T[] } | null>(null);

  useEffect(() => {
    if (!videoId) return;
    let cancelled = false;
    const keep = (items: T[]) => {
      if (!cancelled) setLoaded({ id: videoId, items });
    };
    fetch(getApiUrl(`/videos/${videoId}/${resource}`))
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => keep(Array.isArray(data) ? data : []))
      .catch(() => keep([]));
    return () => {
      cancelled = true;
    };
  }, [videoId, getApiUrl, resource]);

  return videoId && loaded?.id === videoId ? loaded.items : EMPTY;
}
