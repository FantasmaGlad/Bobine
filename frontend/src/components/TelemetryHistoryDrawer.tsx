"use client";

import React, { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import DrawerHeader from "@/components/telemetry/DrawerHeader";
import {
  historyTimeFormatter, periodShortKey, RANGE_LABEL_KEYS, type ApiPeriod, type DrawerPeriod, type RangePeriod,
} from "@/components/telemetry/historyPeriods";
import TelemetryChart from "@/components/telemetry/TelemetryChart";
import TelemetryStats from "@/components/telemetry/TelemetryStats";
import { useEscapeToClose, useTelemetryHistory } from "@/components/telemetry/useTelemetryHistory";

export interface TelemetryHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  metric: string;
  title: string;
  iconName: string;
  rangePeriod?: RangePeriod;
}

export default function TelemetryHistoryDrawer({
  isOpen,
  onClose,
  metric,
  title,
  iconName,
  rangePeriod = "7d",
}: TelemetryHistoryDrawerProps) {
  const { t, language } = useAppSettings();
  const locale = language === "fr" ? "fr-FR" : "en-US";
  const [period, setPeriod] = useState<DrawerPeriod>("range");
  const apiPeriod: ApiPeriod = period === "range" ? rangePeriod : period;
  const { loading, historyData, hoverIndex, setHoverIndex } = useTelemetryHistory(isOpen, metric, apiPeriod);
  useEscapeToClose(isOpen, onClose);

  if (!isOpen) return null;

  const unit = historyData?.unit || "";
  const minVal = historyData?.min ?? 0;
  const maxVal = historyData?.max ?? (unit === "%" ? 100 : 10);

  return (
    <>
      <div className="telemetry-drawer-overlay" onClick={onClose} aria-hidden="true" />
      <aside className="telemetry-drawer" role="dialog" aria-modal="true" aria-label={t("telemetryDrawer.ariaHistory", { title })}>
        <DrawerHeader iconName={iconName} title={title} subtitle={t(RANGE_LABEL_KEYS[apiPeriod])} onClose={onClose} t={t} />
        <div className="telemetry-drawer-filters">
          {(["1h", "6h", "24h", "range"] as const).map((p) => (
            <button key={p} type="button" className={`telemetry-filter-btn ${period === p ? "active" : ""}`} onClick={() => setPeriod(p)} disabled={loading}>
              {t(periodShortKey(p, rangePeriod))}
            </button>
          ))}
        </div>
        <TelemetryStats current={historyData?.current ?? 0} average={historyData?.avg ?? 0} min={minVal} max={maxVal} unit={unit} />
        <TelemetryChart
          points={historyData?.points || []}
          min={minVal}
          max={maxVal}
          unit={unit}
          hoverIndex={hoverIndex}
          onHover={setHoverIndex}
          formatTime={historyTimeFormatter(apiPeriod, locale)}
        />
        <div className="telemetry-drawer-footer">
          <Icon name="info" size={16} />
          <span>{t("telemetryDrawer.footer")}</span>
        </div>
      </aside>
    </>
  );
}
