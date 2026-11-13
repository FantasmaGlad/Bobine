"use client";

import { useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { toOccurrenceDateString, type Occurrence } from "@/lib/scheduleTime";
import type { ShowToast } from "@/lib/useToast";

export function useOccurrenceControls(showToast: ShowToast, onChanged: () => void, onEdit: (scheduleId: number) => void) {
  const { t } = useAppSettings();
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [replacingKey, setReplacingKey] = useState<string | null>(null);
  const [replaceValue, setReplaceValue] = useState("");

  const request = async (path: string, init: RequestInit, done: string, failed: string) => {
    try {
      const res = await fetch(getApiUrl(path), init);
      if (!res.ok) {
        showToast(t(failed), "error");
        return;
      }
      showToast(t(done));
      setReplacingKey(null);
      setExpandedKey(null);
      onChanged();
    } catch {
      showToast(t("schedule.networkError"), "error");
    }
  };

  const override = (o: Occurrence, body: Record<string, unknown>, done: string, failed: string) =>
    request(`/schedule/${o.schedule_id}/overrides`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ occurrence_date: toOccurrenceDateString(o.run_at), ...body }),
    }, done, failed);

  const cancel = (o: Occurrence) => override(o, { action: "cancelled" }, "schedule.cancelledToast", "schedule.cancelError");

  const restore = (o: Occurrence) => {
    if (!o.override_id) return;
    request(`/schedule/${o.schedule_id}/overrides/${o.override_id}`, { method: "DELETE" }, "schedule.restoredToast", "schedule.restoreError");
  };

  const replace = (o: Occurrence) => {
    if (!replaceValue) return;
    const [type, id] = replaceValue.split(":");
    override(o, { action: "replaced", replacement_target_type: type, replacement_target_id: Number(id) }, "schedule.replacedToast", "schedule.replaceError");
  };

  const toggle = (key: string) => {
    setReplacingKey(null);
    setExpandedKey((current) => (current === key ? null : key));
  };

  const startReplace = (key: string) => {
    setReplaceValue("");
    setReplacingKey(key);
  };

  return { expandedKey, replacingKey, replaceValue, setReplaceValue, toggle, startReplace, cancel, restore, replace, edit: onEdit };
}

export type OccurrenceControls = ReturnType<typeof useOccurrenceControls>;
