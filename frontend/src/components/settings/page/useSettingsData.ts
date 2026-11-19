"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import type { SettingsData } from "../types";

export function useSettingsData() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingNetwork, setRefreshingNetwork] = useState(false);
  const fetchSettings = useCallback(() => fetch(getApiUrl("/settings"), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : null))
    .then((d) => {
      if (d) setData(d);
    })
    .catch(() => {})
    .finally(() => setLoading(false)), []);

  const refreshNetwork = () => {
    setRefreshingNetwork(true);
    void fetchSettings().finally(() => setRefreshingNetwork(false));
  };

  useEffect(() => {
    void fetchSettings();
    const id = setInterval(() => void fetchSettings(), 15000);
    return () => clearInterval(id);
  }, [fetchSettings]);

  return { data, setData, loading, refreshingNetwork, refreshNetwork };
}
