import { useCallback, useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { useUploadManager } from "@/lib/UploadManager";
import type { ShowToast } from "@/lib/useToast";
import type { Announcement, Rule } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

function putAnnouncement(id: number, body: Record<string, unknown>) {
  return fetch(getApiUrl(`/radio/announcements/${id}`), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function useRefreshOnImported(fetchAll: () => void) {
  const { uploads } = useUploadManager();
  const seenDoneIds = useRef<Set<string>>(new Set());
  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => u.kind === "radio_announcement_files" && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    fetchAll();
  }, [uploads, fetchAll]);
}

export function useAnnouncements(t: Translate, showToast: ShowToast) {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(() => {
    Promise.all([
      fetch(getApiUrl("/radio/announcements"), { cache: "no-store" }).then((r) => (r.ok ? r.json() : [])),
      fetch(getApiUrl("/radio/announcement-rules"), { cache: "no-store" }).then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([a, r]) => {
        setAnnouncements(a);
        setRules(r);
      })
      .catch(() => showToast(t("radioAnnouncements.genericError"), "error"))
      .finally(() => setLoading(false));
  }, [showToast, t]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);
  useRefreshOnImported(fetchAll);

  const toggleEnabled = async (a: Announcement) => {
    const res = await putAnnouncement(a.id, { enabled: !a.enabled });
    if (res.ok) setAnnouncements((prev) => prev.map((x) => (x.id === a.id ? { ...x, enabled: !x.enabled } : x)));
    else showToast(t("radioAnnouncements.genericError"), "error");
  };

  const saveDescription = async (id: number, value: string): Promise<boolean> => {
    if (!value.trim()) return false;
    const res = await putAnnouncement(id, { description: value.trim() });
    if (!res.ok) {
      showToast(t("radioAnnouncements.genericError"), "error");
      return false;
    }
    showToast(t("radioAnnouncements.updatedToast"));
    fetchAll();
    return true;
  };

  const remove = async (id: number) => {
    const res = await fetch(getApiUrl(`/radio/announcements/${id}`), { method: "DELETE" });
    if (res.ok) {
      showToast(t("radioAnnouncements.deletedToast"));
      setAnnouncements((prev) => prev.filter((a) => a.id !== id));
    } else {
      showToast(t("radioAnnouncements.genericError"), "error");
    }
  };

  return { announcements, rules, setRules, loading, fetchAll, toggleEnabled, saveDescription, remove };
}
