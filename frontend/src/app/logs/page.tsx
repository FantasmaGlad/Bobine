"use client";
import PageNav from "@/components/PageNav";
import React, { useCallback, useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import ActivityTable from "@/components/logs/ActivityTable";
import { eventTypeLabel, type ActivityLogEntry } from "@/components/logs/events";
import { getApiUrl } from "@/lib/apiUrl";

export default function LogsPage() {
  const { t, language } = useAppSettings();
  const eventLabel = (type: string) => eventTypeLabel(type, t);
  const [tab, setTab] = useState<"activity" | "technical">("activity");
  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [technicalLog, setTechnicalLog] = useState("");
  const [technicalLoading, setTechnicalLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [purgeCount, setPurgeCount] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(false);

  const loadActivity = useCallback(() => {
    const qs = filter ? `?event_type=${encodeURIComponent(filter)}` : "";
    fetch(getApiUrl(`/logs/activity${qs}`), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, [filter]);

  const fetchActivity = () => {
    setLoading(true);
    setSelectedIds([]);
    loadActivity();
  };

  const activityRequest = tab === "activity" ? filter : null;
  const [shownActivity, setShownActivity] = useState<string | null>(null);
  if (shownActivity !== activityRequest) {
    setShownActivity(activityRequest);
    if (activityRequest !== null) {
      setLoading(true);
      setSelectedIds([]);
    }
  }

  const toggleSelected = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleSelectAll = () => {
    setSelectedIds((prev) => (prev.length === entries.length ? [] : entries.map((e) => e.id)));
  };

  const deleteActivity = (params: { ids?: number[]; limit?: number }, confirmMessage: string) => {
    if (!window.confirm(confirmMessage)) return;
    setDeleting(true);
    setDeleteError(false);
    const qs = new URLSearchParams();
    if (params.ids) params.ids.forEach((id) => qs.append("ids", String(id)));
    if (params.limit) qs.set("limit", String(params.limit));
    fetch(getApiUrl(`/logs/activity?${qs.toString()}`), { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("delete failed");
        setPurgeCount("");
        fetchActivity();
      })
      .catch(() => setDeleteError(true))
      .finally(() => setDeleting(false));
  };

  const clearTechnicalLog = () => {
    if (!window.confirm(t("logs.clearTechnicalConfirm"))) return;
    setDeleting(true);
    setDeleteError(false);
    fetch(getApiUrl("/logs/technical"), { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("delete failed");
        fetchTechnical();
      })
      .catch(() => setDeleteError(true))
      .finally(() => setDeleting(false));
  };

  useEffect(() => {
    fetch(getApiUrl("/logs/activity/event-types"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setEventTypes)
      .catch(() => setEventTypes([]));
  }, []);

  useEffect(() => {
    if (tab === "activity") loadActivity();
  }, [tab, loadActivity]);

  const loadTechnical = useCallback(() => {
    fetch(getApiUrl("/logs/technical"), { cache: "no-store" })
      .then((res) => (res.ok ? res.text() : ""))
      .then(setTechnicalLog)
      .catch(() => setTechnicalLog(t("logs.technicalLoadError")))
      .finally(() => setTechnicalLoading(false));
  }, [t]);

  const fetchTechnical = () => {
    setTechnicalLoading(true);
    loadTechnical();
  };

  const [technicalTab, setTechnicalTab] = useState(false);
  if (technicalTab !== (tab === "technical")) {
    setTechnicalTab(tab === "technical");
    if (tab === "technical") setTechnicalLoading(true);
  }

  useEffect(() => {
    if (tab === "technical") loadTechnical();
  }, [tab, loadTechnical]);

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
          <div className="toolbar-filters" style={{ flexWrap: "wrap", gap: "8px" }}>
            <ResponsiveSelect
              value={filter}
              onChange={setFilter}
              placeholder={t("logs.allEventTypes")}
              title={t("logs.allEventTypes")}
              options={eventTypes.map((eventType) => ({ value: eventType, label: eventLabel(eventType) }))}
            />
            <button className="btn btn-secondary" onClick={fetchActivity}>
              {t("logs.refresh")}
            </button>
            <input
              type="number"
              min={1}
              className="form-control"
              style={{ width: "110px" }}
              placeholder={t("logs.purgeRecentPlaceholder")}
              title={t("logs.purgeRecentLabel")}
              value={purgeCount}
              onChange={(e) => setPurgeCount(e.target.value)}
            />
            <button
              className="btn btn-secondary"
              disabled={deleting || !purgeCount || Number(purgeCount) <= 0}
              onClick={() =>
                deleteActivity(
                  { limit: Number(purgeCount) },
                  t("logs.purgeRecentConfirm", { count: Number(purgeCount) })
                )
              }
            >
              {t("logs.purgeRecentButton")}
            </button>
            {selectedIds.length > 0 && (
              <button
                className="btn btn-danger"
                disabled={deleting}
                onClick={() =>
                  deleteActivity(
                    { ids: selectedIds },
                    t("logs.deleteSelectionConfirm", { count: selectedIds.length })
                  )
                }
              >
                {t("logs.deleteSelection")} ({selectedIds.length})
              </button>
            )}
            <button
              className="btn btn-danger"
              disabled={deleting || entries.length === 0}
              onClick={() => deleteActivity({}, t("logs.clearActivityConfirm"))}
            >
              {t("logs.clearLogs")}
            </button>
          </div>
        ) : (
          <div className="toolbar-filters" style={{ gap: "8px" }}>
            <button className="btn btn-secondary" onClick={fetchTechnical}>
              {t("logs.refresh")}
            </button>
            <button className="btn btn-danger" disabled={deleting || !technicalLog} onClick={clearTechnicalLog}>
              {t("logs.clearLogs")}
            </button>
            <a href={getApiUrl("/logs/technical/download")} download className="btn btn-secondary">
              {t("logs.downloadFullLog")}
            </a>
          </div>
        )}
      </div>

      {tab === "activity" ? (
        <>
          {deleteError && <p className="live-empty">{t("logs.deleteError")}</p>}

          {loading ? (
            <div className="live-empty">{t("logs.loadingActivity")}</div>
          ) : entries.length === 0 ? (
            <div className="live-empty">{t("logs.noActivity")}</div>
          ) : (
            <ActivityTable
              entries={entries} selectedIds={selectedIds} onToggle={toggleSelected} onToggleAll={toggleSelectAll}
              eventLabel={eventLabel} language={language} t={t}
            />
          )}
        </>
      ) : (
        <>
          {deleteError && <p className="live-empty">{t("logs.deleteError")}</p>}
          <div
            className="glass-surface"
            style={{
              padding: "16px",
              fontFamily: "monospace",
              fontSize: "0.75rem",
              color: "var(--text-muted)",
              whiteSpace: "pre-wrap",
              overflowY: "auto",
              maxHeight: "calc(100vh - 260px)",
            }}
          >
            {technicalLoading ? t("logs.loading") : technicalLog || t("logs.emptyTechnicalLog")}
          </div>
        </>
      )}
    </div>
  );
}
