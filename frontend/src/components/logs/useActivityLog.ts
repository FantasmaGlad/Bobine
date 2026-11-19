"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import type { ActivityLogEntry } from "./events";

export function useEventTypes() {
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  useEffect(() => {
    fetch(getApiUrl("/logs/activity/event-types"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setEventTypes)
      .catch(() => setEventTypes([]));
  }, []);
  return eventTypes;
}

export function useActivityLog(active: boolean) {
  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

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

  const activityRequest = active ? filter : null;
  const [shownActivity, setShownActivity] = useState<string | null>(null);
  if (shownActivity !== activityRequest) {
    setShownActivity(activityRequest);
    if (activityRequest !== null) {
      setLoading(true);
      setSelectedIds([]);
    }
  }

  useEffect(() => {
    if (active) loadActivity();
  }, [active, loadActivity]);

  const toggleSelected = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };
  const toggleSelectAll = () => {
    setSelectedIds((prev) => (prev.length === entries.length ? [] : entries.map((e) => e.id)));
  };

  return { entries, filter, setFilter, loading, selectedIds, fetchActivity, toggleSelected, toggleSelectAll };
}
