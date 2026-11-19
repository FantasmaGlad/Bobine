"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import type { useUploadManager } from "@/lib/UploadManager";
import type { ShowToast } from "@/lib/useToast";
import type { BackgroundItem } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;
type Upload = ReturnType<typeof useUploadManager>["uploads"][number];

function useDefaultCoachBackground(t: Translate, showToast: ShowToast) {
  const [defaultCoachBgId, setDefaultCoachBgId] = useState<number | null>(null);
  const fetchSettings = useCallback(() => fetch(getApiUrl("/settings"), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (data) setDefaultCoachBgId(typeof data.default_coach_background_id === "number" ? data.default_coach_background_id : null);
    })
    .catch(() => {}), []);

  const handleToggleDefaultCoach = async (bgId: number) => {
    const newId = defaultCoachBgId === bgId ? null : bgId;
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ default_coach_background_id: newId }),
      });
      if (res.ok) {
        setDefaultCoachBgId(newId);
        showToast(
          newId !== null
            ? t("backgrounds.defaultSetToast")
            : t("backgrounds.defaultClearedToast"),
          "success"
        );
      } else {
        showToast(t("backgrounds.defaultErrorToast"), "error");
      }
    } catch {
      showToast(t("backgrounds.defaultErrorToast"), "error");
    }
  };

  return { defaultCoachBgId, setDefaultCoachBgId, fetchSettings, handleToggleDefaultCoach };
}

export function useBackgroundLibrary(t: Translate, showToast: ShowToast, uploads: Upload[]) {
  const [backgrounds, setBackgrounds] = useState<BackgroundItem[]>([]);
  const [loading, setLoading] = useState(true);
  const seenDoneIds = useRef<Set<string>>(new Set());
  const { defaultCoachBgId, setDefaultCoachBgId, fetchSettings, handleToggleDefaultCoach } = useDefaultCoachBackground(t, showToast);

  const fetchBackgrounds = useCallback(() => fetch(getApiUrl("/backgrounds"), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setBackgrounds(await res.json());
      else showToast(t("backgrounds.fetchError"), "error");
    })
    .catch(() => showToast(t("backgrounds.connectionError"), "error"))
    .finally(() => setLoading(false)), [showToast, t]);

  useEffect(() => {
    void fetchBackgrounds();
    void fetchSettings();
  }, [fetchBackgrounds, fetchSettings]);

  useEffect(() => {
    const newlyDone = uploads.filter(
      (u) => (u.kind === "background" || u.kind === "background_zip") && u.status === "done" && !seenDoneIds.current.has(u.id)
    );
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    void fetchBackgrounds();
  }, [uploads, fetchBackgrounds]);

  const deleteBackground = async (target: BackgroundItem) => {
    const res = await fetch(getApiUrl(`/backgrounds/${target.id}`), { method: "DELETE" });
    if (res.ok) {
      showToast(t("backgrounds.deletedToast"));
      setBackgrounds((prev) => prev.filter((b) => b.id !== target.id));
      if (defaultCoachBgId === target.id) setDefaultCoachBgId(null);
    } else {
      showToast(t("backgrounds.deleteError"), "error");
    }
    return res.ok;
  };

  return { backgrounds, defaultCoachBgId, loading, handleToggleDefaultCoach, deleteBackground };
}
