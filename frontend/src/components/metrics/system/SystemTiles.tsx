"use client";

import TelemetryTile from "@/components/metrics/TelemetryTile";
import { formatBinarySize } from "@/lib/format";
import { energyLabel, percentText, ramLabel, storageFigures, type SystemTelemetry } from "./systemTelemetry";

type T = (key: string, params?: Record<string, string | number>) => string;
type Open = (metric: string, title: string, iconName: string) => void;

function Temp({ value }: { value: number | null | undefined }) {
  return value != null && <span className="metrics-telemetry-temp">{value.toFixed(0)} °C</span>;
}

function ProcessorTiles({ telemetry, t, openDrawer }: { telemetry: SystemTelemetry | null; t: T; openDrawer: Open }) {
  return (
    <>
      <TelemetryTile name={t("metricsPage.cpu")} icon="memory" ariaLabel={t("metricsPage.ariaCpu")}
        onOpen={() => openDrawer("cpu", t("metricsPage.drawerCpu"), "memory")}
        component={telemetry?.cpu_name || t("common.processor")} componentTitle={telemetry?.cpu_name}
        value={percentText(telemetry?.cpu_percent)}
        detail={<Temp value={telemetry?.cpu_temp_c} />} />
      <TelemetryTile name={t("metricsPage.gpu")} icon="videogame_asset" ariaLabel={t("metricsPage.ariaGpu")}
        onOpen={() => openDrawer("gpu", t("metricsPage.drawerGpu"), "videogame_asset")}
        component={telemetry?.gpu_name || "Puce Graphique"} componentTitle={telemetry?.gpu_name || "Puce Graphique"}
        value={percentText(telemetry?.gpu_percent)}
        detail={<Temp value={telemetry?.gpu_temp_c} />} />
    </>
  );
}

function MemoryTiles({ telemetry, t, openDrawer }: { telemetry: SystemTelemetry | null; t: T; openDrawer: Open }) {
  const ram = ramLabel(telemetry, t);
  const storage = storageFigures(telemetry);
  return (
    <>
      <TelemetryTile name={t("metricsPage.ram")} icon="developer_board" ariaLabel={t("metricsPage.ariaRam")}
        onOpen={() => openDrawer("memory", t("metricsPage.drawerRam"), "developer_board")}
        component={ram} componentTitle={ram}
        value={percentText(telemetry?.memory_percent)}
        detail={<span className="metrics-telemetry-temp">{formatBinarySize(telemetry?.memory_used_bytes, "0 Go")} / {formatBinarySize(telemetry?.memory_total_bytes, "0 Go")}</span>} />
      <TelemetryTile name={t("metricsPage.storage")} icon="storage" ariaLabel={t("metricsPage.ariaStorage")}
        onOpen={() => openDrawer("storage", t("metricsPage.drawerStorage"), "storage")}
        component={telemetry?.storage_model || t("common.mainDisk")} componentTitle={telemetry?.storage_model || t("common.mainDisk")}
        value={`${storage.usedPct.toFixed(0)}%`}
        detail={<span className="metrics-telemetry-temp">{t("metricsPage.storageFree", { free: formatBinarySize(storage.free, "0 Go"), total: formatBinarySize(storage.total, "0 Go") })}</span>} />
    </>
  );
}

export default function SystemTiles(props: { telemetry: SystemTelemetry | null; t: T; openDrawer: Open }) {
  const { telemetry, t, openDrawer } = props;
  return (
    <section className="metrics-telemetry-grid">
      <ProcessorTiles {...props} />
      <MemoryTiles {...props} />
      <TelemetryTile name={t("metricsPage.powerAndEnergy")} icon="bolt" ariaLabel={t("metricsPage.ariaPower")}
        onOpen={() => openDrawer("power", t("metricsPage.drawerPower"), "bolt")}
        component={energyLabel(telemetry, t)} valueStyle={{ color: "var(--accent-text)" }}
        value={telemetry?.power_watts != null ? `${telemetry.power_watts.toFixed(1)} W` : "-- W"} />
      <TelemetryTile name={t("metricsPage.runtime")} icon="timer"
        component={t("metricsPage.systemUptime", { value: telemetry?.runtime?.uptime_formatted || "--" })}
        valueStyle={{ fontSize: "1.4rem", color: "var(--accent-text)" }}
        value={telemetry?.runtime?.app_runtime_formatted || "--"}
        detail={<span className="metrics-telemetry-temp">{t("metricsPage.bobineService")}</span>} />
    </section>
  );
}
