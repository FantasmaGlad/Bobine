"use client";

import React, { useState, useEffect, useCallback } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { MetricPoint } from "@/lib/telemetryChart";
import TelemetryChart from "@/components/telemetry/TelemetryChart";
import TelemetryStats from "@/components/telemetry/TelemetryStats";

export interface TelemetryHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  metric: string;
  title: string;
  iconName: string;
  rangePeriod?: "7d" | "30d" | "this_month" | "all";
}

type ApiPeriod = "1h" | "6h" | "24h" | "7d" | "30d" | "this_month" | "all";

const RANGE_LABEL_KEYS: Record<ApiPeriod, string> = {
  "1h": "telemetryDrawer.range1h",
  "6h": "telemetryDrawer.range6h",
  "24h": "telemetryDrawer.range24h",
  "7d": "telemetryDrawer.range7d",
  "30d": "telemetryDrawer.range30d",
  this_month: "telemetryDrawer.rangeMonth",
  all: "telemetryDrawer.rangeAll",
};

const RANGE_SHORT_KEYS: Record<"7d" | "30d" | "this_month" | "all", string> = {
  "7d": "telemetryDrawer.short7d",
  "30d": "telemetryDrawer.short30d",
  this_month: "telemetryDrawer.shortMonth",
  all: "telemetryDrawer.shortAll",
};

interface HistoryResponse {
  metric: string;
  label: string;
  unit: string;
  period: string;
  points: MetricPoint[];
  current: number;
  min: number;
  max: number;
  avg: number;
  count: number;
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
  const [period, setPeriod] = useState<"1h" | "6h" | "24h" | "range">("range");
  const apiPeriod: ApiPeriod = period === "range" ? rangePeriod : period;
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

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const points = historyData?.points || [];
  const unit = historyData?.unit || "";
  const minVal = historyData?.min ?? 0;
  const maxVal = historyData?.max ?? (unit === "%" ? 100 : 10);
  const avgVal = historyData?.avg ?? 0;
  const curVal = historyData?.current ?? 0;

  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      if (apiPeriod !== "1h" && apiPeriod !== "6h" && apiPeriod !== "24h") {
        return d.toLocaleDateString(locale, { weekday: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
      }
      return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    } catch {
      return isoString;
    }
  };

  return (
    <>
      <div
        className="telemetry-drawer-overlay"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className="telemetry-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={t("telemetryDrawer.ariaHistory", { title })}
      >
        <div className="telemetry-drawer-header">
          <div className="telemetry-drawer-title-wrap">
            <div className="telemetry-drawer-icon" style={{ color: "var(--accent-text)" }}>
              <Icon name={iconName} size={22} />
            </div>
            <div>
              <h2 className="telemetry-drawer-title">{title}</h2>
              <span className="telemetry-drawer-subtitle">
                {t(RANGE_LABEL_KEYS[apiPeriod])}
              </span>
            </div>
          </div>
          <button
            type="button"
            className="close-btn"
            onClick={onClose}
            aria-label={t("telemetryDrawer.close")}
          >
            <Icon name="close" size={20} />
          </button>
        </div>

        <div className="telemetry-drawer-filters">
          {(["1h", "6h", "24h", "range"] as const).map((p) => (
            <button
              key={p}
              type="button"
              className={`telemetry-filter-btn ${period === p ? "active" : ""}`}
              onClick={() => setPeriod(p)}
              disabled={loading}
            >
              {p === "1h" ? t("telemetryDrawer.short1h") : p === "6h" ? t("telemetryDrawer.short6h") : p === "24h" ? t("telemetryDrawer.short24h") : t(RANGE_SHORT_KEYS[rangePeriod])}
            </button>
          ))}
        </div>

        <TelemetryStats current={curVal} average={avgVal} min={minVal} max={maxVal} unit={unit} />

        <TelemetryChart
          points={points}
          min={minVal}
          max={maxVal}
          unit={unit}
          hoverIndex={hoverIndex}
          onHover={setHoverIndex}
          formatTime={formatTime}
        />

        <div className="telemetry-drawer-footer">
          <Icon name="info" size={16} />
          <span>
            {t("telemetryDrawer.footer")}
          </span>
        </div>
      </aside>
    </>
  );
}
