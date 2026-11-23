"use client";

import React, { useCallback, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import AttendanceChart from "@/components/metrics/AttendanceChart";
import CourseRanking from "@/components/metrics/CourseRanking";
import FilterGroup from "@/components/metrics/FilterGroup";
import KpiCard from "@/components/metrics/KpiCard";
import RatingBars from "@/components/metrics/RatingBars";
import type { DashboardMetrics } from "@/components/metrics/types";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { OUTPUTS, type OutputId } from "@/lib/outputs";

type Period = "7d" | "30d" | "this_month" | "all";
type Channel = "all" | OutputId;

function useDashboard(period: Period, channel: Channel) {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const fetchDashboard = useCallback(() => fetch(getApiUrl(`/metrics/dashboard?period=${period}&channel=${channel}`))
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (data) setMetrics(data);
    })
    .catch((err) => console.error("Erreur chargement métriques cours:", err)), [period, channel]);
  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);
  useEffect(() => {
    const id = setInterval(fetchDashboard, 15000);
    return () => clearInterval(id);
  }, [fetchDashboard]);
  return metrics;
}

export default function MetricsCoursesPage() {
  const { t } = useAppSettings();
  const [period, setPeriod] = useState<Period>("7d");
  const [channel, setChannel] = useState<Channel>("all");
  const metrics = useDashboard(period, channel);
  const kpis = metrics?.kpis;
  const ratingBreakdown = metrics?.rating_breakdown || [];
  const completed = t("metricsPage.kpiSessionsCompleted", { count: kpis?.completed_sessions ?? 0 });

  return (
    <div className="metrics-page">
      <div className="metrics-filters-bar" style={{ marginTop: 0 }}>
        <FilterGroup icon="date_range" label={t("metricsPage.periodLabel")} value={period} onChange={setPeriod} choices={[
          { value: "7d", label: t("metricsPage.period7d") },
          { value: "30d", label: t("metricsPage.period30d") },
          { value: "this_month", label: t("metricsPage.periodMonth") },
          { value: "all", label: t("metricsPage.periodAll") },
        ]} />
        <FilterGroup icon="tune" label={t("metricsPage.channelLabel")} value={channel} onChange={setChannel} choices={[
          { value: "all", label: t("metricsPage.channelAll") },
          ...OUTPUTS.map((output) => ({
            value: output.id,
            label: output.wired ? t("metricsPage.channelCable") : t("metricsPage.channelNetwork", { output: t(`outputs.${output.id}`) }),
            icon: output.wired ? "cable" : "wifi",
          })),
        ]} />
      </div>

      <section className="metrics-kpis-grid">
        <KpiCard title={t("metricsPage.kpiSatisfaction")} icon="star" filled unit="/ 5"
          value={kpis?.average_satisfaction != null ? kpis.average_satisfaction.toFixed(1) : "--"}
          detail={t("metricsPage.kpiSatisfactionCount", { count: kpis?.ratings_count ?? 0 })}>
          {ratingBreakdown.length > 0 && <RatingBars breakdown={ratingBreakdown} />}
        </KpiCard>
        <KpiCard title={t("metricsPage.kpiCompletionRate")} icon="task_alt" unit="%"
          value={kpis?.completion_rate != null ? kpis.completion_rate.toFixed(0) : "0"} detail={t("metricsPage.kpiCompletionDesc")}>
          <div className="metrics-kpi-extra">
            <Icon name="check_circle" size={14} />
            <span>{completed}{" "}/ {kpis?.total_sessions ?? 0}</span>
          </div>
        </KpiCard>
        <KpiCard title={t("metricsPage.kpiBroadcastHours")} icon="schedule" unit="h"
          value={kpis?.total_broadcast_hours != null ? kpis.total_broadcast_hours.toFixed(1) : "0.0"} detail={t("metricsPage.kpiBroadcastDesc")} />
        <KpiCard title={t("metricsPage.kpiTotalSessions")} icon="play_circle" unit={t("metricsPage.sessionsCount")}
          value={kpis?.total_sessions ?? 0} detail={completed} />
      </section>

      <AttendanceChart hourly={metrics?.hourly_attendance || []} peakHours={metrics?.peak_hours} />
      <CourseRanking courses={metrics?.top_courses || []} />
    </div>
  );
}
