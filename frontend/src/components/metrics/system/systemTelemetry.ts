import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";

export interface SystemTelemetry {
  cpu_percent: number;
  cpu_name?: string;
  cpu_temp_c?: number | null;
  gpu_percent?: number | null;
  gpu_name?: string | null;
  gpu_temp_c?: number | null;
  memory_total_bytes: number;
  memory_used_bytes: number;
  memory_percent: number;
  ram_brand?: string | null;
  ram_type?: string | null;
  ram_freq?: string | null;
  ram_model?: string | null;
  power_watts?: number | null;
  storage_model?: string;
  storage_used_percent?: number;
  storage_free_bytes?: number;
  storage_total_bytes?: number;
  storage?: {
    total_bytes: number;
    used_bytes: number;
    free_bytes: number;
    used_percent: number;
  };
  runtime?: {
    uptime_seconds: number;
    uptime_formatted: string;
    app_runtime_seconds: number;
    app_runtime_formatted: string;
    cumulative_energy_wh?: number;
    average_power_watts?: number | null;
  };
}

type T = (key: string, params?: Record<string, string | number>) => string;

export function useSystemTelemetry() {
  const [telemetry, setTelemetry] = useState<SystemTelemetry | null>(null);
  const fetchTelemetry = useCallback(() => fetch(getApiUrl("/settings/system"), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (data) setTelemetry(data);
    })
    .catch((err) => console.error("Erreur chargement télémétrie système:", err)), []);

  useEffect(() => {
    fetchTelemetry();
  }, [fetchTelemetry]);

  useEffect(() => {
    const id = setInterval(fetchTelemetry, 5000);
    return () => clearInterval(id);
  }, [fetchTelemetry]);

  return telemetry;
}

export function ramLabel(telemetry: SystemTelemetry | null, t: T): string {
  if (telemetry?.ram_model) return telemetry.ram_model;
  if (!telemetry?.ram_type) return t("metricsPage.ramFallback");
  return `${telemetry.ram_brand ? telemetry.ram_brand + " " : ""}${telemetry.ram_type}${telemetry.ram_freq ? " " + telemetry.ram_freq : ""}`;
}

export function energyLabel(telemetry: SystemTelemetry | null, t: T): string {
  const runtime = telemetry?.runtime;
  if (runtime?.cumulative_energy_wh == null) return t("metricsPage.systemPower");
  const average = runtime.average_power_watts != null ? runtime.average_power_watts.toFixed(1) + " W" : "--";
  return t("metricsPage.energySummary", { total: runtime.cumulative_energy_wh.toFixed(1), average });
}

export function storageFigures(telemetry: SystemTelemetry | null) {
  return {
    free: telemetry?.storage_free_bytes ?? telemetry?.storage?.free_bytes ?? 0,
    total: telemetry?.storage_total_bytes ?? telemetry?.storage?.total_bytes ?? 0,
    usedPct: telemetry?.storage_used_percent ?? telemetry?.storage?.used_percent ?? 0,
  };
}

export function percentText(value: number | null | undefined): string {
  return `${value != null ? value.toFixed(0) : "0"}%`;
}
