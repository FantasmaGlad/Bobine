"use client";

import { useEffect, useRef, useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { recallCatalog, rememberCatalog } from "@/lib/sessionCatalog";
import { useUploadManager } from "@/lib/UploadManager";
import type { ShowToast } from "@/lib/useToast";

import type { AudioCourseSummary, BackgroundOption } from "./types";

const CACHE_KEY = "audio.courses";

function loadJson<T>(path: string, apply: (data: T) => void) {
  fetch(getApiUrl(path), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => data !== null && apply(data))
    .catch(() => {});
}

export function useAudioCourses(showToast: ShowToast) {
  const { t } = useAppSettings();
  const [courses, setCourses] = useState<AudioCourseSummary[]>(() => recallCatalog<AudioCourseSummary>(CACHE_KEY) ?? []);
  const [loading, setLoading] = useState(() => recallCatalog<AudioCourseSummary>(CACHE_KEY) === undefined);
  const [backgrounds, setBackgrounds] = useState<BackgroundOption[]>([]);
  const [programs, setPrograms] = useState<string[]>([]);
  const [defaultBackgroundId, setDefaultBackgroundId] = useState<number | null>(null);
  const { uploads } = useUploadManager();
  const seenDoneIds = useRef<Set<string>>(new Set());

  const fetchCourses = async () => {
    if (recallCatalog<AudioCourseSummary>(CACHE_KEY) === undefined) setLoading(true);
    try {
      const res = await fetch(getApiUrl("/audio"), { cache: "no-store" });
      if (!res.ok) return showToast(t("audio.fetchError"), "error");
      const data = await res.json();
      setCourses(data);
      rememberCatalog(CACHE_KEY, data as AudioCourseSummary[]);
    } catch {
      showToast(t("audio.connectionError"), "error");
    } finally {
      setLoading(false);
    }
  };

  const fetchPrograms = () => loadJson<string[]>("/audio/programs", (data) => setPrograms(Array.isArray(data) ? data : []));

  useEffect(() => {
    fetchCourses();
    loadJson<BackgroundOption[]>("/backgrounds", setBackgrounds);
    fetchPrograms();
    loadJson<{ default_coach_background_id?: unknown }>("/settings", (data) => {
      if (typeof data.default_coach_background_id === "number") setDefaultBackgroundId(data.default_coach_background_id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const newlyDone = uploads.filter((u) => (u.kind === "audio_files" || u.kind === "audio_zip") && u.status === "done" && !seenDoneIds.current.has(u.id));
    if (newlyDone.length === 0) return;
    newlyDone.forEach((u) => seenDoneIds.current.add(u.id));
    fetchCourses();
    fetchPrograms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploads]);

  const defaultBackground = defaultBackgroundId ? backgrounds.find((b) => b.id === defaultBackgroundId) ?? null : null;

  const refresh = () => {
    fetchCourses();
    fetchPrograms();
  };

  return { courses, setCourses, loading, backgrounds, programs, defaultBackground, refresh };
}

export type AudioCourses = ReturnType<typeof useAudioCourses>;
