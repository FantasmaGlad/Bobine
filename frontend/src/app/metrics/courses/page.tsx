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
}

export default function MetricsCoursesPage() {
  const { t } = useAppSettings();
  const [period, setPeriod] = useState<"7d" | "30d" | "this_month" | "all">("7d");
  const [channel, setChannel] = useState<"all" | "cable" | "network">("all");
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`/api/metrics/dashboard?period=${period}&channel=${channel}`);
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error("Erreur chargement métriques cours:", err);
    }
  }, [period, channel]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Actualisation discrète toutes les 15 secondes
  useEffect(() => {
    const id = setInterval(fetchDashboard, 15000);
    return () => clearInterval(id);
  }, [fetchDashboard]);

  const kpis = metrics?.kpis;
  const ratingBreakdown = metrics?.rating_breakdown || [];
  const hourly = metrics?.hourly_attendance || [];
  const maxHourlySessions = Math.max(1, ...(hourly.length ? hourly.map((h) => Number(h?.sessions) || 0) : [1]));
  const courses = metrics?.top_courses || [];

  return (
    <div className="metrics-page">
      {/* Barre de filtres épurée (Période & Canal) */}
      <div className="metrics-filters-bar" style={{ marginTop: 0 }}>
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

      {/* Histogramme d'affluence 24h CSS */}
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

      {/* Palmarès des Cours (Leaderboard) avec icône moderne et teintes dynamiques */}
      <section className="metrics-section-card">
        <div className="metrics-section-header">
          <div>
            <h3>
              <Icon name="leaderboard" size={20} /> {t("metricsPage.rankingTitle")}
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
                  <th style={{ textAlign: "center" }}>{t("metricsPage.thSessions")}</th>
                  <th style={{ textAlign: "center" }}>{t("metricsPage.thCompletion")}</th>
                  <th style={{ textAlign: "right" }}>{t("metricsPage.thRating")}</th>
                </tr>
              </thead>
              <tbody>
                {courses.map((course, idx) => {
                  const rank = idx + 1;
                  const rankClass = rank === 1 ? "rank-1" : rank === 2 ? "rank-2" : rank === 3 ? "rank-3" : "";
                  return (
                    <tr key={course.video_id}>
                      <td className="metrics-rank-cell">
                        <span className={`metrics-rank-badge ${rankClass}`}>{rank}</span>
                      </td>
                      <td>
                        <div className="metrics-course-cell">
                          <div className="metrics-course-info">
                            <span className="metrics-course-title">{course.title}</span>
                            <span className="metrics-course-program">{course.program || "Autre"}</span>
                          </div>
                        </div>
                      </td>
                      <td style={{ textAlign: "center", fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>
                        {course.total_sessions}
                      </td>
                      <td>
                        <div className="metrics-table-progress-wrap">
                          <div className="metrics-table-progress-bar">
                            <div
                              className="metrics-table-progress-fill"
                              style={{ width: `${course.completion_rate}%` }}
                            />
                          </div>
                          <span className="metrics-table-progress-text">{course.completion_rate.toFixed(0)}%</span>
                        </div>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {course.average_rating != null && course.ratings_count > 0 ? (
                          <div className="metrics-table-rating">
                            <span style={{ color: "var(--accent-primary)" }}>★</span>
                            <span>{course.average_rating.toFixed(1)}</span>
                            <span className="metrics-table-rating-count">({course.ratings_count})</span>
                          </div>
                        ) : (
                          <span className="metrics-no-rating">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="metrics-empty">
            <p>{t("metricsPage.emptyCourses")}</p>
          </div>
        )}
      </section>
    </div>
  );
}
