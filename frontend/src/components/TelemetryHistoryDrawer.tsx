"use client";

import React, { useState, useEffect, useCallback, useId } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

export interface TelemetryHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  metric: string;
  title: string;
  iconName: string;
  /** Période choisie dans le bandeau de la page, appliquée au bouton « Période » du tiroir. */
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

interface MetricPoint {
  timestamp: string;
  value: number;
}

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
  const gradientId = useId();
  // « range » = la période du bandeau de la page (7 j, 30 j, mois en cours, tout l'historique conservé).
  const [period, setPeriod] = useState<"1h" | "6h" | "24h" | "range">("range");
  const apiPeriod: ApiPeriod = period === "range" ? rangePeriod : period;
  const [loading, setLoading] = useState(false);
  const [historyData, setHistoryData] = useState<HistoryResponse | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const fetchHistory = useCallback(async () => {
    if (!metric) return;
    try {
      setLoading(true);
      const res = await fetch(`/api/metrics/hardware/history?metric=${encodeURIComponent(metric)}&period=${apiPeriod}`);
      if (res.ok) {
        const data: HistoryResponse = await res.json();
        setHistoryData(data);
      }
    } catch (err) {
      console.error("Erreur chargement historique télémétrie:", err);
    } finally {
      setLoading(false);
    }
  }, [metric, apiPeriod]);

  useEffect(() => {
    if (isOpen) {
      fetchHistory();
      setHoverIndex(null);
    }
  }, [isOpen, fetchHistory]);

  // Fermeture par touche Échap
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

  // Calcul du tracé SVG
  const svgWidth = 460;
  const svgHeight = 220;
  const padLeft = 46;
  const padRight = 20;
  const padTop = 24;
  const padBottom = 32;

  const plotW = svgWidth - padLeft - padRight;
  const plotH = svgHeight - padTop - padBottom;

  // Échelle Y avec marge
  let yMin = Math.floor(Math.min(...(points.length ? points.map((p) => p.value) : [0]), minVal));
  let yMax = Math.ceil(Math.max(...(points.length ? points.map((p) => p.value) : [100]), maxVal));
  if (unit === "%") {
    yMin = Math.max(0, yMin - 5);
    yMax = Math.min(100, Math.max(10, yMax + 5));
  } else {
    const range = Math.max(1, yMax - yMin);
    yMin = Math.max(0, Math.floor(yMin - range * 0.1));
    yMax = Math.ceil(yMax + range * 0.1);
  }
  const ySpan = Math.max(1, yMax - yMin);

  const coords = points.map((pt, idx) => {
    const x = padLeft + (points.length > 1 ? (idx / (points.length - 1)) * plotW : plotW / 2);
    const normY = (pt.value - yMin) / ySpan;
    const y = padTop + plotH - normY * plotH;
    return { x, y, pt };
  });

  // Construction de la ligne SVG
  let pathD = "";
  if (coords.length > 0) {
    pathD = `M ${coords[0].x} ${coords[0].y}`;
    for (let i = 1; i < coords.length; i++) {
      pathD += ` L ${coords[i].x} ${coords[i].y}`;
    }
  }

  // Construction de l'aire fermée
  let areaD = "";
  if (coords.length > 0) {
    const bottomY = padTop + plotH;
    areaD = `${pathD} L ${coords[coords.length - 1].x} ${bottomY} L ${coords[0].x} ${bottomY} Z`;
  }

  // Formatage horodatage
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

  const hoveredPoint = hoverIndex !== null && coords[hoverIndex] ? coords[hoverIndex] : null;

  return (
    <>
      {/* Overlay sombre accessible */}
      <div
        className="telemetry-drawer-overlay"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Tiroir latéral droit */}
      <aside
        className="telemetry-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={t("telemetryDrawer.ariaHistory", { title })}
      >
        {/* En-tête du tiroir */}
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

        {/* Sélecteur de période temporelle */}
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

        {/* Synthèse des statistiques clés */}
        <div className="telemetry-stats-grid">
          <div className="telemetry-stat-card">
            <span className="telemetry-stat-label">{t("telemetryDrawer.current")}</span>
            <span className="telemetry-stat-val" style={{ color: "var(--accent-text)" }}>
              {curVal.toFixed(1)} <small>{unit}</small>
            </span>
          </div>
          <div className="telemetry-stat-card">
            <span className="telemetry-stat-label">{t("telemetryDrawer.average")}</span>
            <span className="telemetry-stat-val">
              {avgVal.toFixed(1)} <small>{unit}</small>
            </span>
          </div>
          <div className="telemetry-stat-card">
            <span className="telemetry-stat-label">{t("telemetryDrawer.min")}</span>
            <span className="telemetry-stat-val">
              {minVal.toFixed(1)} <small>{unit}</small>
            </span>
          </div>
          <div className="telemetry-stat-card">
            <span className="telemetry-stat-label">{t("telemetryDrawer.max")}</span>
            <span className="telemetry-stat-val">
              {maxVal.toFixed(1)} <small>{unit}</small>
            </span>
          </div>
        </div>

        {/* Section Graphique Temporel */}
        <div className="telemetry-chart-container">
          <div className="telemetry-chart-head">
            <span className="telemetry-chart-caption">
              {t("telemetryDrawer.evolution")}
            </span>
            {hoveredPoint && (
              <span className="telemetry-chart-hover-pill">
                <strong>{hoveredPoint.pt.value.toFixed(1)} {unit}</strong> — {formatTime(hoveredPoint.pt.timestamp)}
              </span>
            )}
          </div>

          <div className="telemetry-svg-wrapper">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="telemetry-svg"
              onMouseLeave={() => setHoverIndex(null)}
            >
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent-primary)" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="var(--accent-primary)" stopOpacity="0.01" />
                </linearGradient>
              </defs>

              {/* Lignes de repère horizontales */}
              {[0, 0.5, 1].map((ratio) => {
                const y = padTop + plotH * (1 - ratio);
                const val = yMin + ySpan * ratio;
                return (
                  <g key={ratio} className="telemetry-grid-line-group">
                    <line
                      x1={padLeft}
                      y1={y}
                      x2={svgWidth - padRight}
                      y2={y}
                      stroke="var(--border-color)"
                      strokeDasharray="4 4"
                      strokeWidth="1"
                    />
                    <text
                      x={padLeft - 6}
                      y={y + 4}
                      textAnchor="end"
                      fontSize="10"
                      fill="var(--text-muted)"
                      fontFamily="inherit"
                    >
                      {val.toFixed(0)}
                    </text>
                  </g>
                );
              })}

              {/* Aire sous la courbe */}
              {areaD && <path d={areaD} fill={`url(#${gradientId})`} />}

              {/* Ligne de tendance principale */}
              {pathD && (
                <path
                  d={pathD}
                  fill="none"
                  stroke="var(--accent-text)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              )}

              {/* Points interactifs / réticule au survol */}
              {hoveredPoint && (
                <g className="telemetry-hover-group">
                  <line
                    x1={hoveredPoint.x}
                    y1={padTop}
                    x2={hoveredPoint.x}
                    y2={padTop + plotH}
                    stroke="var(--text-muted)"
                    strokeDasharray="3 3"
                    strokeWidth="1"
                  />
                  <circle
                    cx={hoveredPoint.x}
                    cy={hoveredPoint.y}
                    r="5"
                    fill="var(--bg-surface)"
                    stroke="var(--accent-text)"
                    strokeWidth="3"
                  />
                </g>
              )}

              {/* Zones invisibles pour interaction souris/tactile fluide */}
              {coords.map((c, i) => {
                const colW = plotW / Math.max(1, coords.length);
                return (
                  <rect
                    key={i}
                    x={c.x - colW / 2}
                    y={padTop}
                    width={colW}
                    height={plotH}
                    fill="transparent"
                    style={{ cursor: "crosshair" }}
                    onMouseEnter={() => setHoverIndex(i)}
                    onTouchStart={() => setHoverIndex(i)}
                  />
                );
              })}

              {/* Repères d'horodatage en bas */}
              {coords.length > 0 && (
                <>
                  <text
                    x={padLeft}
                    y={svgHeight - 10}
                    textAnchor="start"
                    fontSize="10"
                    fill="var(--text-muted)"
                    fontFamily="inherit"
                  >
                    {formatTime(coords[0].pt.timestamp)}
                  </text>
                  <text
                    x={svgWidth - padRight}
                    y={svgHeight - 10}
                    textAnchor="end"
                    fontSize="10"
                    fill="var(--text-muted)"
                    fontFamily="inherit"
                  >
                    {formatTime(coords[coords.length - 1].pt.timestamp)}
                  </text>
                </>
              )}
            </svg>
          </div>
        </div>

        {/* Note d'information */}
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
