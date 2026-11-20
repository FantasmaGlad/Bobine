import { useCallback, useEffect, useRef, useState } from "react";
import { devicesRequest } from "@/lib/devices/request";
import { type ApiError } from "@/lib/apiError";

export function useDevicesResource<T>(path: string, refreshKey: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);

  const reload = useCallback(() => devicesRequest<T>(path).then((result) => {
    if (!alive.current) return;
    if (result.ok) {
      setData(result.data);
      setError(null);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }), [path]);

  useEffect(() => {
    alive.current = true;
    void reload();
    return () => {
      alive.current = false;
    };
  }, [reload, refreshKey]);

  return { data, error, loading, reload };
}
