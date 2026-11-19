"use client";

import ResponsiveSelect from "@/components/ResponsiveSelect";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

interface ActivityToolbarProps {
  t: Translate;
  eventTypes: string[];
  eventLabel: (type: string) => string;
  filter: string;
  setFilter: (value: string) => void;
  fetchActivity: () => void;
  deleting: boolean;
  selectedIds: number[];
  entryCount: number;
  purgeCount: string;
  setPurgeCount: (value: string) => void;
  deleteActivity: (params: { ids?: number[]; limit?: number }, confirmMessage: string) => void;
}

export default function ActivityToolbar({ t, eventTypes, eventLabel, filter, setFilter, fetchActivity, deleting, selectedIds, entryCount, purgeCount, setPurgeCount, deleteActivity }: ActivityToolbarProps) {
  return (
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
        disabled={deleting || entryCount === 0}
        onClick={() => deleteActivity({}, t("logs.clearActivityConfirm"))}
      >
        {t("logs.clearLogs")}
      </button>
    </div>
  );
}
