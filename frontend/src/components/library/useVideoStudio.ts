"use client";

import React, { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/lib/apiError";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { formatCleanDescription } from "@/lib/formatDescription";
import type { ShowToast } from "@/lib/useToast";

import type { Video, VideoSubtitleItem } from "./types";

type Translate = ReturnType<typeof useAppSettings>["t"];

async function normalizeVideo(base: string, t: Translate, showToast: ShowToast) {
  try {
    const res = await fetch(getApiUrl(`${base}/normalize`), { method: "POST" });
    const data = await res.json();
    if (res.ok) showToast(data.message, "success");
    else showToast(errorMessage(data, t("library.normalizeError")), "error");
  } catch {
    showToast(t("library.normalizeNetworkError"), "error");
  }
}

function useVideoSubtitles(base: string, showToast: ShowToast) {
  const { t } = useAppSettings();
  const [subtitles, setSubtitles] = useState<VideoSubtitleItem[]>([]);

  const fetchSubtitles = useCallback(() => fetch(getApiUrl(`${base}/subtitles`))
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (data !== null) setSubtitles(Array.isArray(data) ? data : []);
    })
    .catch(() => {}), [base]);

  useEffect(() => {
    void fetchSubtitles();
  }, [fetchSubtitles]);

  const uploadSubtitle = async (file: File) => {
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(getApiUrl(`${base}/subtitles`), { method: "POST", body });
      if (res.ok) {
        showToast(t("library.subtitleAdded"), "success");
        fetchSubtitles();
      } else {
        const errData = await res.json().catch(() => ({}));
        showToast(errorMessage(errData, t("library.subtitleImportError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  const deleteSubtitle = async (subId: number) => {
    try {
      const res = await fetch(getApiUrl(`${base}/subtitles/${subId}`), { method: "DELETE" });
      if (res.ok) {
        showToast(t("library.subtitleDeleted"), "success");
        setSubtitles((prev) => prev.filter((s) => s.id !== subId));
      } else {
        showToast(t("library.subtitleDeleteError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  return { subtitles, uploadSubtitle, deleteSubtitle };
}

function useThumbnailUpload(base: string, showToast: ShowToast, onUpdated: (video: Video) => void, saveFailed: (res: Response) => Promise<void>) {
  const { t } = useAppSettings();
  const [uploadingThumbnail, setUploadingThumbnail] = useState(false);
  const uploadThumbnail = async (file: File) => {
    setUploadingThumbnail(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(getApiUrl(`${base}/thumbnail`), { method: "PUT", body });
      if (res.ok) {
        showToast(t("library.thumbnailSaved"));
        onUpdated(await res.json());
      } else {
        await saveFailed(res);
      }
    } catch {
      showToast(t("library.saveConnectionError"), "error");
    } finally {
      setUploadingThumbnail(false);
    }
  };

  return { uploadingThumbnail, uploadThumbnail };
}

export function useVideoStudio(video: Video, showToast: ShowToast, onUpdated: (video: Video) => void) {
  const { t } = useAppSettings();
  const [title, setTitle] = useState(video.title);
  const [program, setProgram] = useState(video.program || "");
  const [release, setRelease] = useState(video.release || "");
  const [description, setDescription] = useState(video.description || "");
  const [saving, setSaving] = useState(false);
  const base = `/videos/${video.id}`;
  const { subtitles, uploadSubtitle, deleteSubtitle } = useVideoSubtitles(base, showToast);

  const saveFailed = async (res: Response) => {
    const errData = await res.json();
    showToast(t("library.saveErrorDetail", { detail: errorMessage(errData, t("library.saveErrorFallback")) }), "error");
  };

  const { uploadingThumbnail, uploadThumbnail } = useThumbnailUpload(base, showToast, onUpdated, saveFailed);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch(getApiUrl(base), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, program: program.trim() || null, release: release || null, description: formatCleanDescription(description) || null }),
      });
      if (res.ok) {
        showToast(t("library.metadataSaved"));
        onUpdated(await res.json());
      } else {
        await saveFailed(res);
      }
    } catch {
      showToast(t("library.saveConnectionError"), "error");
    } finally {
      setSaving(false);
    }
  };

  const normalize = () => normalizeVideo(base, t, showToast);

  return {
    fields: { title, program, release, description },
    setters: { setTitle, setProgram, setRelease, setDescription },
    saving, uploadingThumbnail, subtitles,
    uploadSubtitle, deleteSubtitle, save, normalize, uploadThumbnail,
  };
}

export type VideoStudioState = ReturnType<typeof useVideoStudio>;
