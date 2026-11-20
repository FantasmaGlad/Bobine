"use client";

import React, { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import FilterGroup from "@/components/metrics/FilterGroup";
import SystemTiles from "@/components/metrics/system/SystemTiles";
import { useSystemTelemetry } from "@/components/metrics/system/systemTelemetry";
import TelemetryHistoryDrawer from "@/components/TelemetryHistoryDrawer";

type Drawer = { metric: string; title: string; iconName: string };

export default function MetricsSystemPage() {
  const { t } = useAppSettings();
  const telemetry = useSystemTelemetry();
  const [period, setPeriod] = useState<"7d" | "30d" | "this_month" | "all">("7d");
  const [activeDrawer, setActiveDrawer] = useState<Drawer | null>(null);
  const openDrawer = (metric: string, title: string, iconName: string) => {
    setActiveDrawer({ metric, title, iconName });
  };

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
      <SystemTiles telemetry={telemetry} t={t} openDrawer={openDrawer} />
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
