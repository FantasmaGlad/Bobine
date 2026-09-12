"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";

interface RatingBreakdown {
  score: number;
  count: number;
  percentage: number;
}

interface CourseStat {
  video_id: number;
  title: string;
  program: string | null;
  thumbnail_path: string | null;
  total_sessions: number;
  completed_sessions: number;
  completion_rate: number;
  total_duration_hours: number;
  average_rating: number | null;
  ratings_count: number;
  sessions_count?: number;
  duration_seconds?: number;
}

interface HourlyAttendance {
  hour: number;
  sessions: number;
}

interface DashboardMetrics {
  period: string;
  channel: string;
  kpis: {
    average_satisfaction: number | null;
    ratings_count: number;
    completion_rate: number;
    total_broadcast_hours: number;
    total_sessions: number;
    completed_sessions: number;
  };
  rating_breakdown: RatingBreakdown[];
  hourly_attendance: HourlyAttendance[];
  peak_hours: number[];
  top_courses: CourseStat[];
  hardware_telemetry: {
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
    };
  };
}

function formatBytes(bytes?: number): string {
  if (!bytes || bytes < 0) return "0 Go";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const val = bytes / Math.pow(1024, i);
  return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export default function MetricsPage() {
  const { t } = useAppSettings();
  const [period, setPeriod] = useState<"7d" | "30d" | "this_month" | "all">("7d");
  const [channel, setChannel] = useState<"all" | "cable" | "network">("all");
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/metrics/dashboard?period=${period}&channel=${channel}`);
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard metrics:", err);
    } finally {
      setLoading(false);
    }
  }, [period, channel]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Periodic refresh for live telemetry (every 10s)
  useEffect(() => {
    const id = setInterval(fetchDashboard, 10000);
    return () => clearInterval(id);
  }, [fetchDashboard]);

  const kpis = metrics?.kpis;
  const ratingBreakdown = metrics?.rating_breakdown || [];
  const hourly = metrics?.hourly_attendance || [];
  const maxHourlySessions = Math.max(1, ...(hourly.length ? hourly.map((h) => Number(h?.sessions) || 0) : [1]));
  const courses = metrics?.top_courses || [];
  const telemetry = metrics?.hardware_telemetry;

  return (
    <div className="metrics-page">
      {/* En-tête de la page */}
      <header className="metrics-header">
        <div className="metrics-header-title-wrap">
          <h1>
            <Icon name="analytics" size={26} /> {t("metricsPage.title")}
          </h1>
          <p className="metrics-subtitle">{t("metricsPage.subtitle")}</p>
        </div>
        <button
          type="button"
          className="btn btn-secondary metrics-refresh-btn"
          onClick={fetchDashboard}
          disabled={loading}
          title="Actualiser les métriques"
        >
          <Icon name="refresh" size={18} className={loading ? "spin" : ""} />
        </button>
      </header>

      {/* Barre de filtres (Période & Canal) */}
      <div className="metrics-filters-bar">
        <div className="metrics-filter-group">
          <span className="metrics-filter-label">
            <Icon name="date_range" size={16} /> {t("metricsPage.periodLabel")} :
          </span>
          <div className="view-toggle">
            <button
              type="button"
              className={`view-btn ${period === "7d" ? "active" : ""}`}
              onClick={() => setPeriod("7d")}
            >
              {t("metricsPage.period7d")}
            </button>
            <button
              type="button"
              className={`view-btn ${period === "30d" ? "active" : ""}`}
              onClick={() => setPeriod("30d")}
            >
              {t("metricsPage.period30d")}
            </button>
            <button
              type="button"
              className={`view-btn ${period === "this_month" ? "active" : ""}`}
              onClick={() => setPeriod("this_month")}
            >
              {t("metricsPage.periodMonth")}
            </button>
            <button
              type="button"
              className={`view-btn ${period === "all" ? "active" : ""}`}
              onClick={() => setPeriod("all")}
            >
              {t("metricsPage.periodAll")}
            </button>
          </div>
        </div>

        <div className="metrics-filter-group">
          <span className="metrics-filter-label">
            <Icon name="tune" size={16} /> {t("metricsPage.channelLabel")} :
          </span>
          <div className="view-toggle">
            <button
              type="button"
              className={`view-btn ${channel === "all" ? "active" : ""}`}
              onClick={() => setChannel("all")}
            >
              {t("metricsPage.channelAll")}
            </button>
            <button
              type="button"
              className={`view-btn ${channel === "cable" ? "active" : ""}`}
              onClick={() => setChannel("cable")}
            >
              <Icon name="cable" size={14} /> {t("metricsPage.channelCable")}
            </button>
            <button
              type="button"
              className={`view-btn ${channel === "network" ? "active" : ""}`}
              onClick={() => setChannel("network")}
            >
              <Icon name="wifi" size={14} /> {t("metricsPage.channelNetwork")}
            </button>
          </div>
        </div>
      </div>

      {/* Cartes KPI Principales */}
      <section className="metrics-kpis-grid">
        {/* 1. Satisfaction Globale */}
        <div className="metrics-kpi-card">
          <div className="metrics-kpi-header">
            <span className="metrics-kpi-title">{t("metricsPage.kpiSatisfaction")}</span>
            <div className="metrics-kpi-icon-wrap" style={{ color: "var(--accent-primary)" }}>
              <Icon name="star" size={24} filled />
            </div>
          </div>
          <div className="metrics-kpi-value-row">
            <span className="metrics-kpi-main-num">
              {kpis?.average_satisfaction != null ? kpis.average_satisfaction.toFixed(1) : "--"}
            </span>
            <span className="metrics-kpi-unit">/ 5</span>
          </div>
          <p className="metrics-kpi-detail">
            {t("metricsPage.kpiSatisfactionCount", { count: kpis?.ratings_count ?? 0 })}
          </p>

          {/* Répartition des étoiles */}
          {ratingBreakdown.length > 0 && (
            <div className="metrics-rating-bars">
              {[5, 4, 3, 2, 1].map((star) => {
                const item = ratingBreakdown.find((r) => r.score === star);
                const pct = item?.percentage ?? 0;
                return (
                  <div key={star} className="metrics-rating-bar-row">
                    <span className="metrics-rating-star-num">{star}★</span>
                    <div className="metrics-rating-bar-track">
                      <div className="metrics-rating-bar-fill" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="metrics-rating-bar-pct">{pct.toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 2. Taux de Complétion */}
        <div className="metrics-kpi-card">
          <div className="metrics-kpi-header">
            <span className="metrics-kpi-title">{t("metricsPage.kpiCompletionRate")}</span>
            <div className="metrics-kpi-icon-wrap" style={{ color: "var(--accent-primary)" }}>
              <Icon name="task_alt" size={24} />
            </div>
          </div>
          <div className="metrics-kpi-value-row">
            <span className="metrics-kpi-main-num">
              {kpis?.completion_rate != null ? kpis.completion_rate.toFixed(0) : "0"}
            </span>
            <span className="metrics-kpi-unit">%</span>
          </div>
          <p className="metrics-kpi-detail">{t("metricsPage.kpiCompletionDesc")}</p>
          <div className="metrics-kpi-extra">
            <Icon name="check_circle" size={14} />
            <span>
              {t("metricsPage.kpiSessionsCompleted", {
                count: kpis?.completed_sessions ?? 0,
              })}{" "}
              / {kpis?.total_sessions ?? 0}
            </span>
          </div>
        </div>

        {/* 3. Volume de Diffusion */}
        <div className="metrics-kpi-card">
          <div className="metrics-kpi-header">
            <span className="metrics-kpi-title">{t("metricsPage.kpiBroadcastHours")}</span>
            <div className="metrics-kpi-icon-wrap" style={{ color: "var(--accent-primary)" }}>
              <Icon name="schedule" size={24} />
            </div>
          </div>
          <div className="metrics-kpi-value-row">
            <span className="metrics-kpi-main-num">
              {kpis?.total_broadcast_hours != null ? kpis.total_broadcast_hours.toFixed(1) : "0.0"}
            </span>
            <span className="metrics-kpi-unit">h</span>
          </div>
          <p className="metrics-kpi-detail">{t("metricsPage.kpiBroadcastDesc")}</p>
        </div>

        {/* 4. Séances Lancées */}
        <div className="metrics-kpi-card">
          <div className="metrics-kpi-header">
            <span className="metrics-kpi-title">{t("metricsPage.kpiTotalSessions")}</span>
            <div className="metrics-kpi-icon-wrap" style={{ color: "var(--accent-primary)" }}>
              <Icon name="play_circle" size={24} />
            </div>
          </div>
          <div className="metrics-kpi-value-row">
            <span className="metrics-kpi-main-num">{kpis?.total_sessions ?? 0}</span>
            <span className="metrics-kpi-unit">{t("metricsPage.sessionsCount")}</span>
          </div>
          <p className="metrics-kpi-detail">
            {t("metricsPage.kpiSessionsCompleted", { count: kpis?.completed_sessions ?? 0 })}
          </p>
        </div>
      </section>

      {/* Grille intermédiaire : Histogramme d'affluence 24h & Télémétrie en direct */}
      <div className="metrics-split-row">
        {/* Histogramme 24h CSS */}
        <section className="metrics-section-card metrics-chart-card">
          <div className="metrics-section-header">
            <div>
              <h3>
                <Icon name="bar_chart" size={20} /> {t("metricsPage.chartTitle")}
              </h3>
              <p className="metrics-section-subtitle">{t("metricsPage.chartSubtitle")}</p>
            </div>
            {metrics?.peak_hours && metrics.peak_hours.length > 0 && (
              <span className="metrics-peak-badge">
                <Icon name="trending_up" size={14} />
                {t("metricsPage.peakHours", {
                  hours: metrics.peak_hours.map((h) => `${h}h`).join(", "),
                })}
              </span>
            )}
          </div>

          <div className="metrics-histogram-container">
            <div className="metrics-histogram-bars">
              {hourly.map((item) => {
                const sessCount = Number(item?.sessions) || 0;
                const heightPct = Math.max(4, Math.min(100, (sessCount / (maxHourlySessions || 1)) * 100));
                const isPeak = metrics?.peak_hours?.includes(item.hour);
                return (
                  <div key={item.hour} className="metrics-histogram-column">
                    <div
                      className={`metrics-histogram-bar ${isPeak ? "peak" : ""}`}
                      style={{ height: `${heightPct}%` }}
                      title={`${item.hour}h:00 — ${sessCount} ${t("metricsPage.sessionsCount")}`}
                    >
                      <span className="metrics-histogram-tooltip">{sessCount}</span>
                    </div>
                    <span className="metrics-histogram-label">
                      {item.hour % 3 === 0 ? `${item.hour}h` : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Télémétrie Matérielle en Direct */}
        <section className="metrics-section-card metrics-telemetry-card">
          <div className="metrics-section-header">
            <div>
              <h3>
                <Icon name="monitor_heart" size={20} /> {t("metricsPage.telemetryTitle")}
              </h3>
              <p className="metrics-section-subtitle">{t("metricsPage.telemetrySubtitle")}</p>
            </div>
          </div>

          <div className="metrics-telemetry-grid">
            {/* CPU */}
            <div className="metrics-telemetry-item">
              <div className="metrics-telemetry-item-head">
                <Icon name="memory" size={18} />
                <span className="metrics-telemetry-name">{t("metricsPage.cpu")}</span>
              </div>
              <span className="metrics-telemetry-component-name">
                {telemetry?.cpu_name || "CPU"}
              </span>
              <div className="metrics-telemetry-metric-val">
                <strong>{telemetry?.cpu_percent != null ? telemetry.cpu_percent.toFixed(0) : "0"}%</strong>
                {telemetry?.cpu_temp_c != null && (
                  <span className="metrics-telemetry-temp">{telemetry.cpu_temp_c.toFixed(0)} °C</span>
                )}
              </div>
            </div>

            {/* GPU */}
            {telemetry && (telemetry.gpu_percent != null || telemetry.gpu_name) && (
              <div className="metrics-telemetry-item">
                <div className="metrics-telemetry-item-head">
                  <Icon name="videogame_asset" size={18} />
                  <span className="metrics-telemetry-name">{t("metricsPage.gpu")}</span>
                </div>
                <span className="metrics-telemetry-component-name">
                  {telemetry.gpu_name || "GPU"}
                </span>
                <div className="metrics-telemetry-metric-val">
                  <strong>{telemetry.gpu_percent != null ? telemetry.gpu_percent.toFixed(0) : "0"}%</strong>
                  {telemetry.gpu_temp_c != null && (
                    <span className="metrics-telemetry-temp">{telemetry.gpu_temp_c.toFixed(0)} °C</span>
                  )}
                </div>
              </div>
            )}

            {/* Puissance (W) */}
            {telemetry?.power_watts != null && (
              <div className="metrics-telemetry-item">
                <div className="metrics-telemetry-item-head">
                  <Icon name="bolt" size={18} style={{ color: "var(--accent-warning)" }} />
                  <span className="metrics-telemetry-name">{t("metricsPage.power")}</span>
                </div>
                <span className="metrics-telemetry-component-name">Alimentation directe</span>
                <div className="metrics-telemetry-metric-val">
                  <strong style={{ color: "var(--accent-warning)" }}>
                    {telemetry.power_watts.toFixed(1)} W
                  </strong>
                </div>
              </div>
            )}

            {/* RAM */}
            <div className="metrics-telemetry-item">
              <div className="metrics-telemetry-item-head">
                <Icon name="developer_board" size={18} />
                <span className="metrics-telemetry-name">{t("metricsPage.ram")}</span>
              </div>
              <span className="metrics-telemetry-component-name">
                {telemetry?.ram_model || (telemetry?.ram_type ? `${telemetry.ram_brand ? telemetry.ram_brand + " " : ""}${telemetry.ram_type}${telemetry.ram_freq ? " " + telemetry.ram_freq : ""}` : "Mémoire vive")}
              </span>
              <div className="metrics-telemetry-metric-val">
                <strong>{telemetry?.memory_percent != null ? telemetry.memory_percent.toFixed(0) : "0"}%</strong>
                <span className="metrics-telemetry-temp">
                  {formatBytes(telemetry?.memory_used_bytes)} / {formatBytes(telemetry?.memory_total_bytes)}
                </span>
              </div>
            </div>

            {/* Stockage */}
            {telemetry?.storage && (
              <div className="metrics-telemetry-item">
                <div className="metrics-telemetry-item-head">
                  <Icon name="storage" size={18} />
                  <span className="metrics-telemetry-name">{t("metricsPage.storage")}</span>
                </div>
                <span className="metrics-telemetry-component-name">
                  {telemetry.storage_model || "Disque principal"}
                </span>
                <div className="metrics-telemetry-metric-val">
                  <strong>{telemetry.storage.used_percent.toFixed(0)}%</strong>
                  <span className="metrics-telemetry-temp">
                    {formatBytes(telemetry.storage.free_bytes)} libres
                  </span>
                </div>
              </div>
            )}

            {/* Uptime & Runtime */}
            {telemetry?.runtime && (
              <div className="metrics-telemetry-item">
                <div className="metrics-telemetry-item-head">
                  <Icon name="timer" size={18} />
                  <span className="metrics-telemetry-name">{t("metricsPage.runtime")}</span>
                </div>
                <span className="metrics-telemetry-component-name">
                  Uptime: {telemetry.runtime.uptime_formatted}
                </span>
                <div className="metrics-telemetry-metric-val">
                  <span style={{ fontSize: "0.85rem", color: "var(--accent-primary)" }}>
                    {telemetry.runtime.app_runtime_formatted}
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Palmarès des Cours (Leaderboard) */}
      <section className="metrics-section-card">
        <div className="metrics-section-header">
          <div>
            <h3>
              <Icon name="military_tech" size={20} /> {t("metricsPage.rankingTitle")}
            </h3>
            <p className="metrics-section-subtitle">{t("metricsPage.rankingSubtitle")}</p>
          </div>
        </div>

        {courses.length > 0 ? (
          <div className="metrics-table-wrapper">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th style={{ width: "48px" }}>{t("metricsPage.thRank")}</th>
                  <th>{t("metricsPage.thCourse")}</th>
                  <th style={{ textAlign: "right" }}>{t("metricsPage.thSessions")}</th>
                  <th style={{ textAlign: "right" }}>{t("metricsPage.thHours")}</th>
                  <th style={{ textAlign: "center" }}>{t("metricsPage.thCompletion")}</th>
                  <th style={{ textAlign: "right" }}>{t("metricsPage.thRating")}</th>
                </tr>
              </thead>
              <tbody>
                {courses.map((c, index) => {
                  return (
                    <tr key={c.video_id}>
                      <td className="metrics-rank-cell">
                        <span className={`metrics-rank-badge rank-${index + 1}`}>{index + 1}</span>
                      </td>
                      <td className="metrics-course-cell">
                        <div className="metrics-course-info">
                          <span className="metrics-course-title">{c.title}</span>
                          {c.program && <span className="metrics-course-program">{c.program}</span>}
                        </div>
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 700 }}>
                        {c.total_sessions ?? c.sessions_count ?? 0}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {(c.total_duration_hours ?? (c.duration_seconds ? ((c.duration_seconds * (c.sessions_count || c.total_sessions || 1)) / 3600) : 0)).toFixed(1)} h
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <div className="metrics-table-progress-wrap">
                          <div className="metrics-table-progress-bar">
                            <div
                              className="metrics-table-progress-fill"
                              style={{ width: `${Math.min(100, Math.max(0, c.completion_rate ?? 0))}%` }}
                            />
                          </div>
                          <span className="metrics-table-progress-text">
                            {(c.completion_rate ?? 0).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {c.average_rating != null ? (
                          <div className="metrics-table-rating">
                            <Icon name="star" size={16} filled style={{ color: "var(--accent-primary)" }} />
                            <span>{(c.average_rating ?? 0).toFixed(1)}</span>
                            <span className="metrics-table-rating-count">({c.ratings_count ?? 0})</span>
                          </div>
                        ) : (
                          <span className="metrics-no-rating">--</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="metrics-empty">{t("metricsPage.noData")}</p>
        )}
      </section>
    </div>
  );
}
