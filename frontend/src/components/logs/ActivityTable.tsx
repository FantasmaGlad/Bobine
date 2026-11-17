"use client";

import React from "react";
import { errorMessage } from "@/lib/apiError";
import type { Language } from "@/lib/i18n";
import { formatTimestamp, type ActivityLogEntry } from "./events";

interface ActivityTableProps {
  entries: ActivityLogEntry[];
  selectedIds: number[];
  onToggle: (id: number) => void;
  onToggleAll: () => void;
  eventLabel: (type: string) => string;
  language: Language;
  t: (key: string) => string;
}

export default function ActivityTable({ entries, selectedIds, onToggle, onToggleAll, eventLabel, language, t }: ActivityTableProps) {
  return (
    <div className="table-wrapper glass-surface">
      <table className="videos-table responsive-table responsive-table--select">
        <thead>
          <tr>
            <th style={{ width: "36px" }}>
              <input
                type="checkbox"
                checked={selectedIds.length === entries.length && entries.length > 0}
                onChange={onToggleAll}
                title={t("logs.selectAll")}
              />
            </th>
            <th style={{ width: "180px" }}>{t("logs.timestampHeader")}</th>
            <th style={{ width: "220px" }}>{t("logs.eventHeader")}</th>
            <th>{t("logs.detailHeader")}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td>
                <input
                  type="checkbox"
                  checked={selectedIds.includes(entry.id)}
                  onChange={() => onToggle(entry.id)}
                />
              </td>
              <td data-label={t("logs.timestampHeader")} style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>
                {formatTimestamp(entry.timestamp, language)}
              </td>
              <td data-label={t("logs.eventHeader")} style={{ fontWeight: 700 }}>{eventLabel(entry.event_type)}</td>
              <td data-label={t("logs.detailHeader")} style={{ color: "var(--text-muted)" }}>{errorMessage(entry, "—")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
