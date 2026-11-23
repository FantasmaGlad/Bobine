"use client";

import Link from "next/link";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatTime } from "@/lib/format";

import type { DashboardData } from "./useDashboardData";

export function CoachModeNotice() {
  const { t } = useAppSettings();
  return (
    <div className="dashboard-root" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "55vh", textAlign: "center", gap: "16px", padding: "40px 20px" }}>
      <div style={{ width: "72px", height: "72px", borderRadius: "50%", background: "color-mix(in srgb, var(--accent-primary) 12%, transparent)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Icon name="mic" size={36} color="var(--accent-text)" />
      </div>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 800, margin: 0 }}>{t("dashboard.coachModeActiveTitle")}</h2>
      <p style={{ color: "var(--text-muted)", maxWidth: "440px", margin: 0, fontSize: "0.9rem", lineHeight: 1.5 }}>{t("dashboard.coachModeActiveDesc")}</p>
      <Link href="/coach/" className="btn btn-primary olc-press" style={{ textDecoration: "none", height: "46px", padding: "0 28px", display: "inline-flex", alignItems: "center", gap: "8px", fontWeight: 700 }}>
        <Icon name="mic" size={18} />
        {t("dashboard.joinCoachSession")}
      </Link>
    </div>
  );
}

export function InterruptedBanner({ data }: { data: DashboardData }) {
  const { t } = useAppSettings();
  const item = data.interrupted!;
  const coach = item.cause === "coach_priority";
  return (
    <div className="interrupted-block">
      <div className="interrupted-text">
        <span className="interrupted-label">{t(coach ? "dashboard.interruptedCoachLabel" : "dashboard.interruptedScheduleLabel")}</span>
        <span className="interrupted-title">
          {coach ? item.title ?? t("dashboard.scheduledCourseFallback") : `${item.title ?? t("dashboard.courseFallback")} — ${formatTime(item.position_seconds)}`}
        </span>
      </div>
      <div className="interrupted-actions">
        <button className="btn btn-primary" onClick={data.resume} disabled={data.resuming}>
          <Icon name="play_arrow" size={16} filled />
          {data.resuming ? t("dashboard.resuming") : coach ? t("dashboard.launchNow") : t("dashboard.resume")}
        </button>
        <button className="btn btn-secondary" onClick={data.dismiss} disabled={data.resuming}>
          <Icon name="close" size={16} />
          {t("dashboard.dismiss")}
        </button>
      </div>
    </div>
  );
}
