"use client";

import React, { useState, useEffect, useCallback } from "react";
import { formatBinarySize } from "@/lib/format";
import { useAppSettings } from "@/lib/AppSettingsContext";
import FilterGroup from "@/components/metrics/FilterGroup";
import TelemetryTile from "@/components/metrics/TelemetryTile";
import TelemetryHistoryDrawer from "@/components/TelemetryHistoryDrawer";
import { getApiUrl } from "@/lib/apiUrl";

interface SystemTelemetry {
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

export default function MetricsSystemPage() {
  const { t } = useAppSettings();
  const [telemetry, setTelemetry] = useState<SystemTelemetry | null>(null);
  const [period, setPeriod] = useState<"7d" | "30d" | "this_month" | "all">("7d");
  const [activeDrawer, setActiveDrawer] = useState<{
    metric: string;
    title: string;
    iconName: string;
  } | null>(null);

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

  const openDrawer = (metric: string, title: string, iconName: string) => {
    setActiveDrawer({ metric, title, iconName });
  };

  const ramLabel = telemetry?.ram_model || (telemetry?.ram_type ? `${telemetry.ram_brand ? telemetry.ram_brand + " " : ""}${telemetry.ram_type}${telemetry.ram_freq ? " " + telemetry.ram_freq : ""}` : t("metricsPage.ramFallback"));
  const energyLabel = telemetry?.runtime?.cumulative_energy_wh != null
    ? t("metricsPage.energySummary", { total: telemetry.runtime.cumulative_energy_wh.toFixed(1), average: telemetry.runtime.average_power_watts != null ? telemetry.runtime.average_power_watts.toFixed(1) + " W" : "--" })
    : t("metricsPage.systemPower");

  const freeStorage = telemetry?.storage_free_bytes ?? telemetry?.storage?.free_bytes ?? 0;
  const totalStorage = telemetry?.storage_total_bytes ?? telemetry?.storage?.total_bytes ?? 0;
  const usedStoragePct = telemetry?.storage_used_percent ?? telemetry?.storage?.used_percent ?? 0;

  return (
    <div className="metrics-page">
      <div className="metrics-filters-bar" style={{ marginTop: 0 }}>
        <FilterGroup icon="date_range" label={t("metricsPage.periodLabel")} value={period} onChange={setPeriod} choices={[
          { value: "7d", label: t("metricsPage.period7d") },
          { value: "30d", label: t("metricsPage.period30d") },
          { value: "this_month", label: t("metricsPage.periodMonth") },
          { value: "all", label: t("metricsPage.periodAll") },
        ]} />
      </div>

      <section className="metrics-telemetry-grid">
        <TelemetryTile name={t("metricsPage.cpu")} icon="memory" ariaLabel={t("metricsPage.ariaCpu")}
          onOpen={() => openDrawer("cpu", t("metricsPage.drawerCpu"), "memory")}
          component={telemetry?.cpu_name || t("common.processor")} componentTitle={telemetry?.cpu_name}
          value={`${telemetry?.cpu_percent != null ? telemetry.cpu_percent.toFixed(0) : "0"}%`}
          detail={telemetry?.cpu_temp_c != null && <span className="metrics-telemetry-temp">{telemetry.cpu_temp_c.toFixed(0)} °C</span>} />
        <TelemetryTile name={t("metricsPage.gpu")} icon="videogame_asset" ariaLabel={t("metricsPage.ariaGpu")}
          onOpen={() => openDrawer("gpu", t("metricsPage.drawerGpu"), "videogame_asset")}
          component={telemetry?.gpu_name || "Puce Graphique"} componentTitle={telemetry?.gpu_name || "Puce Graphique"}
          value={`${telemetry?.gpu_percent != null ? telemetry.gpu_percent.toFixed(0) : "0"}%`}
          detail={telemetry?.gpu_temp_c != null && <span className="metrics-telemetry-temp">{telemetry.gpu_temp_c.toFixed(0)} °C</span>} />
        <TelemetryTile name={t("metricsPage.ram")} icon="developer_board" ariaLabel={t("metricsPage.ariaRam")}
          onOpen={() => openDrawer("memory", t("metricsPage.drawerRam"), "developer_board")}
          component={ramLabel} componentTitle={ramLabel}
          value={`${telemetry?.memory_percent != null ? telemetry.memory_percent.toFixed(0) : "0"}%`}
          detail={<span className="metrics-telemetry-temp">{formatBinarySize(telemetry?.memory_used_bytes, "0 Go")} / {formatBinarySize(telemetry?.memory_total_bytes, "0 Go")}</span>} />
        <TelemetryTile name={t("metricsPage.storage")} icon="storage" ariaLabel={t("metricsPage.ariaStorage")}
          onOpen={() => openDrawer("storage", t("metricsPage.drawerStorage"), "storage")}
          component={telemetry?.storage_model || t("common.mainDisk")} componentTitle={telemetry?.storage_model || t("common.mainDisk")}
          value={`${usedStoragePct.toFixed(0)}%`}
          detail={<span className="metrics-telemetry-temp">{t("metricsPage.storageFree", { free: formatBinarySize(freeStorage, "0 Go"), total: formatBinarySize(totalStorage, "0 Go") })}</span>} />
        <TelemetryTile name={t("metricsPage.powerAndEnergy")} icon="bolt" ariaLabel={t("metricsPage.ariaPower")}
          onOpen={() => openDrawer("power", t("metricsPage.drawerPower"), "bolt")}
          component={energyLabel} valueStyle={{ color: "var(--accent-text)" }}
          value={telemetry?.power_watts != null ? `${telemetry.power_watts.toFixed(1)} W` : "-- W"} />
        <TelemetryTile name={t("metricsPage.runtime")} icon="timer"
          component={t("metricsPage.systemUptime", { value: telemetry?.runtime?.uptime_formatted || "--" })}
          valueStyle={{ fontSize: "1.4rem", color: "var(--accent-text)" }}
          value={telemetry?.runtime?.app_runtime_formatted || "--"}
          detail={<span className="metrics-telemetry-temp">{t("metricsPage.bobineService")}</span>} />
      </section>

      {activeDrawer && (
        <TelemetryHistoryDrawer
          isOpen={true}
          onClose={() => setActiveDrawer(null)}
          rangePeriod={period}
          metric={activeDrawer.metric}
          title={activeDrawer.title}
          iconName={activeDrawer.iconName}
        />
      )}
    </div>
  );
}
