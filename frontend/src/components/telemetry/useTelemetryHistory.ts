import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { type ApiPeriod, type HistoryResponse } from "./historyPeriods";

export function useTelemetryHistory(isOpen: boolean, metric: string, apiPeriod: ApiPeriod) {
  const [loading, setLoading] = useState(false);
  const [historyData, setHistoryData] = useState<HistoryResponse | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const fetchHistory = useCallback(() => {
    if (!metric) return;
    fetch(getApiUrl(`/metrics/hardware/history?metric=${encodeURIComponent(metric)}&period=${apiPeriod}`))
      .then((res) => (res.ok ? (res.json() as Promise<HistoryResponse>) : null))
      .then((data) => {
        if (data) setHistoryData(data);
      })
      .catch((err) => console.error("Erreur chargement historique télémétrie:", err))
      .finally(() => setLoading(false));
  }, [metric, apiPeriod]);

  const [requested, setRequested] = useState<string | null>(null);
  const request = isOpen ? `${metric}|${apiPeriod}` : null;
  if (requested !== request) {
    setRequested(request);
    if (request) {
      setLoading(true);
      setHoverIndex(null);
    }
  }

  useEffect(() => {
    if (isOpen) fetchHistory();
  }, [isOpen, fetchHistory]);

  return { loading, historyData, hoverIndex, setHoverIndex };
}

export function useEscapeToClose(isOpen: boolean, onClose: () => void) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);
}
