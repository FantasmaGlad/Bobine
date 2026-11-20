import { useCallback, useEffect, useState } from "react";
import { devicesRequest } from "@/lib/devices/request";
import { type AudioDetails } from "@/lib/devices/types";
import { errorText, type SectionProps } from "../../shared/section";

export function useAudioDetails(id: string | null, t: SectionProps["t"]) {
  const [details, setDetails] = useState<AudioDetails | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [detailsFor, setDetailsFor] = useState(id);
  if (detailsFor !== id) {
    setDetailsFor(id);
    if (id) {
      setDetails(null);
      setFailed(null);
    }
  }

  const load = useCallback(() => {
    if (!id) return Promise.resolve();
    return devicesRequest<AudioDetails>(`/audio/details?id=${encodeURIComponent(id)}`).then((result) => {
      if (result.ok) {
        setDetails(result.data);
        setFailed(null);
      } else {
        setFailed(errorText(result.error, t));
      }
    });
  }, [id, t]);

  useEffect(() => {
    if (!id) return;
    void load();
    const timer = setInterval(() => { void load(); }, 2000);
    return () => clearInterval(timer);
  }, [id, load]);

  return { details, failed, load };
}
