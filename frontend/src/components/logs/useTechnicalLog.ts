"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";

export function useTechnicalLog(active: boolean, t: (key: string) => string) {
  const [technicalLog, setTechnicalLog] = useState("");
  const [technicalLoading, setTechnicalLoading] = useState(false);

  const loadTechnical = useCallback(() => {
    fetch(getApiUrl("/logs/technical"), { cache: "no-store" })
      .then((res) => (res.ok ? res.text() : ""))
      .then(setTechnicalLog)
      .catch(() => setTechnicalLog(t("logs.technicalLoadError")))
      .finally(() => setTechnicalLoading(false));
  }, [t]);

  const fetchTechnical = () => {
    setTechnicalLoading(true);
    loadTechnical();
  };

  const [technicalTab, setTechnicalTab] = useState(false);
  if (technicalTab !== active) {
    setTechnicalTab(active);
    if (active) setTechnicalLoading(true);
  }

  useEffect(() => {
    if (active) loadTechnical();
  }, [active, loadTechnical]);

  return { technicalLog, technicalLoading, fetchTechnical };
}
