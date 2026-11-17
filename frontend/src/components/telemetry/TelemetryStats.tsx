"use client";

import React from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";

interface TelemetryStatsProps {
  current: number;
  average: number;
  min: number;
  max: number;
  unit: string;
}

export default function TelemetryStats({ current, average, min, max, unit }: TelemetryStatsProps) {
  const { t } = useAppSettings();
  const cards: Array<[string, number, boolean]> = [
    ["telemetryDrawer.current", current, true],
    ["telemetryDrawer.average", average, false],
    ["telemetryDrawer.min", min, false],
    ["telemetryDrawer.max", max, false],
  ];
  return (
    <div className="telemetry-stats-grid">
      {cards.map(([label, value, accent]) => (
        <div key={label} className="telemetry-stat-card">
          <span className="telemetry-stat-label">{t(label)}</span>
          <span className="telemetry-stat-val" style={accent ? { color: "var(--accent-text)" } : undefined}>
            {value.toFixed(1)} <small>{unit}</small>
          </span>
        </div>
      ))}
    </div>
  );
}
