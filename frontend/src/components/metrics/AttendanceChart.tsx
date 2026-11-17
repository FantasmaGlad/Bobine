"use client";

import React from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { HourlyAttendance } from "./types";

export default function AttendanceChart({ hourly, peakHours }: { hourly: HourlyAttendance[]; peakHours: number[] | undefined }) {
  const { t } = useAppSettings();
  const maxHourlySessions = Math.max(1, ...(hourly.length ? hourly.map((h) => Number(h?.sessions) || 0) : [1]));
  return (
    <section className="metrics-section-card metrics-chart-card">
      <div className="metrics-section-header">
        <div>
          <h3>
            <Icon name="bar_chart" size={20} /> {t("metricsPage.chartTitle")}
          </h3>
          <p className="metrics-section-subtitle">{t("metricsPage.chartSubtitle")}</p>
        </div>
        {peakHours && peakHours.length > 0 && (
          <span className="metrics-peak-badge">
            <Icon name="trending_up" size={14} />
            {t("metricsPage.peakHours", { hours: peakHours.map((h) => `${h}h`).join(", ") })}
          </span>
        )}
      </div>
      <div className="metrics-histogram-container">
        <div className="metrics-histogram-bars">
          {hourly.map((item) => {
            const sessCount = Number(item?.sessions) || 0;
            const heightPct = Math.max(4, Math.min(100, (sessCount / (maxHourlySessions || 1)) * 100));
            const isPeak = peakHours?.includes(item.hour);
            return (
              <div key={item.hour} className="metrics-histogram-column">
                <div
                  className={`metrics-histogram-bar ${isPeak ? "peak" : ""}`}
                  style={{ height: `${heightPct}%` }}
                  title={`${item.hour}h:00 — ${sessCount} ${t("metricsPage.sessionsCount")}`}
                >
                  <span className="metrics-histogram-tooltip">{sessCount}</span>
                </div>
                <span className="metrics-histogram-label">{item.hour % 3 === 0 ? `${item.hour}h` : ""}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
