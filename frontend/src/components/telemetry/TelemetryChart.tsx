"use client";

import React, { useId } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { CHART, PLOT_H, PLOT_W, chartGeometry, type MetricPoint } from "@/lib/telemetryChart";

interface TelemetryChartProps {
  points: MetricPoint[];
  min: number;
  max: number;
  unit: string;
  hoverIndex: number | null;
  onHover: (index: number | null) => void;
  formatTime: (iso: string) => string;
}

const AXIS_TEXT = { fontSize: "10", fill: "var(--text-muted)", fontFamily: "inherit" } as const;

function GridLines({ yMin, ySpan }: { yMin: number; ySpan: number }) {
  return (
    <>
      {[0, 0.5, 1].map((ratio) => {
        const y = CHART.padTop + PLOT_H * (1 - ratio);
        return (
          <g key={ratio} className="telemetry-grid-line-group">
            <line x1={CHART.padLeft} y1={y} x2={CHART.width - CHART.padRight} y2={y} stroke="var(--border-color)" strokeDasharray="4 4" strokeWidth="1" />
            <text x={CHART.padLeft - 6} y={y + 4} textAnchor="end" {...AXIS_TEXT}>{(yMin + ySpan * ratio).toFixed(0)}</text>
          </g>
        );
      })}
    </>
  );
}

export default function TelemetryChart({ points, min, max, unit, hoverIndex, onHover, formatTime }: TelemetryChartProps) {
  const { t } = useAppSettings();
  const gradientId = useId();
  const { yMin, ySpan, coords, pathD, areaD } = chartGeometry(points, min, max, unit);
  const hovered = hoverIndex !== null && coords[hoverIndex] ? coords[hoverIndex] : null;
  const colW = PLOT_W / Math.max(1, coords.length);
  return (
    <div className="telemetry-chart-container">
      <div className="telemetry-chart-head">
        <span className="telemetry-chart-caption">{t("telemetryDrawer.evolution")}</span>
        {hovered && (
          <span className="telemetry-chart-hover-pill">
            <strong>{hovered.pt.value.toFixed(1)} {unit}</strong> — {formatTime(hovered.pt.timestamp)}
          </span>
        )}
      </div>
      <div className="telemetry-svg-wrapper">
        <svg viewBox={`0 0 ${CHART.width} ${CHART.height}`} className="telemetry-svg" onMouseLeave={() => onHover(null)}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-primary)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--accent-primary)" stopOpacity="0.01" />
            </linearGradient>
          </defs>
          <GridLines yMin={yMin} ySpan={ySpan} />
          {areaD && <path d={areaD} fill={`url(#${gradientId})`} />}
          {pathD && <path d={pathD} fill="none" stroke="var(--accent-text)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />}
          {hovered && (
            <g className="telemetry-hover-group">
              <line x1={hovered.x} y1={CHART.padTop} x2={hovered.x} y2={CHART.padTop + PLOT_H} stroke="var(--text-muted)" strokeDasharray="3 3" strokeWidth="1" />
              <circle cx={hovered.x} cy={hovered.y} r="5" fill="var(--bg-surface)" stroke="var(--accent-text)" strokeWidth="3" />
            </g>
          )}
          {coords.map((c, i) => (
            <rect
              key={i}
              x={c.x - colW / 2}
              y={CHART.padTop}
              width={colW}
              height={PLOT_H}
              fill="transparent"
              style={{ cursor: "crosshair" }}
              onMouseEnter={() => onHover(i)}
              onTouchStart={() => onHover(i)}
            />
          ))}
          {coords.length > 0 && (
            <>
              <text x={CHART.padLeft} y={CHART.height - 10} textAnchor="start" {...AXIS_TEXT}>{formatTime(coords[0].pt.timestamp)}</text>
              <text x={CHART.width - CHART.padRight} y={CHART.height - 10} textAnchor="end" {...AXIS_TEXT}>{formatTime(coords[coords.length - 1].pt.timestamp)}</text>
            </>
          )}
        </svg>
      </div>
    </div>
  );
}
