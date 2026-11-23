"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import Icon from "@/components/Icon";
import UpcomingCourse from "@/components/UpcomingCourse";
import { useAppSettings } from "@/lib/AppSettingsContext";

import type { OccurrenceSummary } from "./types";

function ActionCard({ icon, kind, title, desc, children }: { icon: string; kind: string; title: string; desc: string; children: ReactNode }) {
  return (
    <div className="live-block bento-action-card">
      <div className="bento-action-header">
        <div className={`bento-action-icon ${kind}`}><Icon name={icon} size={20} /></div>
        <div><h3 className="bento-action-title">{title}</h3></div>
      </div>
      <p className="bento-action-desc">{desc}</p>
      {children}
    </div>
  );
}

export function ActionCards({ isCable, locked, onAmbiance }: { isCable: boolean; locked: boolean; onAmbiance: () => void }) {
  const { t } = useAppSettings();
  return (
    <div className="bento-actions-grid">
      {isCable && (
        <ActionCard icon="mic" kind="coach" title={t("dashboard.coachCardTitle")} desc={t("dashboard.coachCardDesc")}>
          <Link href="/coach/" className="btn btn-primary bento-action-btn olc-press">
            <Icon name="mic" size={16} />
            {t("dashboard.switchToCoach")}
          </Link>
        </ActionCard>
      )}
      <ActionCard icon="wallpaper" kind="ambiance" title={t("dashboard.ambianceCardTitle")} desc={t("dashboard.ambianceCardDesc")}>
        <button type="button" className="btn btn-secondary bento-action-btn olc-press" onClick={onAmbiance} disabled={locked}>
          <Icon name="wallpaper" size={16} />
          {t("dashboard.launchAmbiance")}
        </button>
      </ActionCard>
    </div>
  );
}

export function UpcomingList({ channel, upcoming }: { channel: string; upcoming: OccurrenceSummary[] }) {
  const { t, language } = useAppSettings();
  const locale = language === "fr" ? "fr-FR" : "en-US";
  return (
    <div className="live-block">
      <div className="live-header">
        <h3>
          <Icon name="schedule" size={18} />
          {t("dashboard.upcomingTitle")}
        </h3>
        <a href={`/schedule/?channel=${channel}`} className="status-pill" style={{ textDecoration: "none" }}>
          <Icon name="calendar_month" size={14} />
          {t("dashboard.viewSchedule")}
        </a>
      </div>
      {upcoming.length === 0 ? (
        <p className="live-empty">{t("dashboard.noUpcoming")}</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {upcoming.map((o, idx) => (
            <UpcomingCourse key={`${o.schedule_id}-${idx}`} occurrence={o} fallbackTitle={t("dashboard.courseFallback")}
              when={new Date(o.run_at).toLocaleString(locale, { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })} />
          ))}
        </div>
      )}
    </div>
  );
}
