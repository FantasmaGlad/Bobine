"use client";

import React from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

interface TelemetryTileProps {
  name: string;
  icon: string;
  component: string;
  componentTitle?: string;
  value: React.ReactNode;
  valueStyle?: React.CSSProperties;
  detail?: React.ReactNode;
  onOpen?: () => void;
  ariaLabel?: string;
}

export default function TelemetryTile({ name, icon, component, componentTitle, value, valueStyle, detail, onOpen, ariaLabel }: TelemetryTileProps) {
  const { t } = useAppSettings();
  const interactive = onOpen !== undefined;
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (onOpen && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      onOpen();
    }
  };
  return (
    <div
      className={`metrics-telemetry-item${interactive ? " interactive" : ""}`}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onOpen}
      onKeyDown={interactive ? onKeyDown : undefined}
      aria-label={ariaLabel}
    >
      <div className="metrics-telemetry-item-head">
        <span className="metrics-telemetry-name">{name}</span>
        <div className="metrics-kpi-icon-wrap" style={{ color: "var(--accent-text)" }}>
          <Icon name={icon} size={24} />
        </div>
      </div>
      <span className="metrics-telemetry-component-name" title={componentTitle}>{component}</span>
      <div className="metrics-telemetry-metric-val">
        <span className="metrics-telemetry-big-num" style={valueStyle}>{value}</span>
        {detail}
      </div>
      {interactive ? (
        <span className="metrics-telemetry-cta">
          {t("metricsPage.history")} <Icon name="chevron_right" size={14} />
        </span>
      ) : (
        <div style={{ marginTop: "auto" }} />
      )}
    </div>
  );
}
