"use client";
import PageNav from "@/components/PageNav";
import { oneOf } from "@/lib/urlView";
import { useUrlView } from "@/lib/useUrlView";
import React, { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import ActivityTable from "@/components/logs/ActivityTable";
import ActivityToolbar from "@/components/logs/ActivityToolbar";
import { eventTypeLabel } from "@/components/logs/events";
import TechnicalLogView from "@/components/logs/TechnicalLogView";
import TechnicalToolbar from "@/components/logs/TechnicalToolbar";
import { useActivityLog, useEventTypes } from "@/components/logs/useActivityLog";
import { useLogDeletion } from "@/components/logs/useLogDeletion";
import { useTechnicalLog } from "@/components/logs/useTechnicalLog";

const LOG_VIEWS = oneOf(["activity", "technical"] as const, "activity");

export default function LogsPage() {
  const { t, language } = useAppSettings();
  const eventLabel = (type: string) => eventTypeLabel(type, t);
  const [tab, setTab] = useUrlView("vue", LOG_VIEWS);
  const eventTypes = useEventTypes();
  const activity = useActivityLog(tab === "activity");
  const technical = useTechnicalLog(tab === "technical", t);
  const { deleting, deleteError, remove } = useLogDeletion();
  const [purgeCount, setPurgeCount] = useState("");

  const deleteActivity = (params: { ids?: number[]; limit?: number }, confirmMessage: string) => {
    const qs = new URLSearchParams();
    if (params.ids) params.ids.forEach((id) => qs.append("ids", String(id)));
    if (params.limit) qs.set("limit", String(params.limit));
    remove(`/logs/activity?${qs.toString()}`, confirmMessage, () => { setPurgeCount(""); activity.fetchActivity(); });
  };
  const clearTechnicalLog = () => remove("/logs/technical", t("logs.clearTechnicalConfirm"), technical.fetchTechnical);

  return (
    <div className="library-container">
      <PageNav
        tabs={[{ id: "activity", label: t("logs.activityTab") }, { id: "technical", label: t("logs.technicalTab") }]}
        value={tab}
        onChange={(id) => setTab(id as typeof tab)}
        ariaLabel={t("logs.activityTab")}
      />
      <div className="library-toolbar sticky-glass-toolbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>

        {tab === "activity" ? (
          <ActivityToolbar t={t} eventTypes={eventTypes} eventLabel={eventLabel} filter={activity.filter} setFilter={activity.setFilter}
            fetchActivity={activity.fetchActivity} deleting={deleting} selectedIds={activity.selectedIds}
            entryCount={activity.entries.length} purgeCount={purgeCount} setPurgeCount={setPurgeCount} deleteActivity={deleteActivity} />
        ) : (
          <TechnicalToolbar t={t} fetchTechnical={technical.fetchTechnical} clearTechnicalLog={clearTechnicalLog}
            deleting={deleting} technicalLog={technical.technicalLog} />
        )}
      </div>

      {tab === "activity" ? (
        <>
          {deleteError && <p className="live-empty">{t("logs.deleteError")}</p>}

          {activity.loading ? (
            <div className="live-empty">{t("logs.loadingActivity")}</div>
          ) : activity.entries.length === 0 ? (
            <div className="live-empty">{t("logs.noActivity")}</div>
          ) : (
            <ActivityTable
              entries={activity.entries} selectedIds={activity.selectedIds} onToggle={activity.toggleSelected} onToggleAll={activity.toggleSelectAll}
              eventLabel={eventLabel} language={language} t={t}
            />
          )}
        </>
      ) : (
        <>
          {deleteError && <p className="live-empty">{t("logs.deleteError")}</p>}
          <TechnicalLogView text={technical.technicalLoading ? t("logs.loading") : technical.technicalLog || t("logs.emptyTechnicalLog")} />
        </>
      )}
    </div>
  );
}
