"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";
import type { Occurrence } from "@/lib/scheduleTime";

export default function OccurrenceBadges({ occurrence }: { occurrence: Occurrence }) {
  const { t } = useAppSettings();
  return (
    <>
      {occurrence.override_action === "replaced" && <span className="schedule-occurrence-badge">{t("schedule.replacedBadge")}</span>}
      {occurrence.override_action === "cancelled" && <span className="schedule-occurrence-badge">{t("schedule.cancelledBadge")}</span>}
    </>
  );
}
