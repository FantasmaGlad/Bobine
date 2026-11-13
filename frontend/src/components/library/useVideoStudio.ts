"use client";

import React, { useEffect, useState } from "react";

import { errorMessage } from "@/lib/apiError";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { formatCleanDescription } from "@/lib/formatDescription";
import type { ShowToast } from "@/lib/useToast";

import type { Video, VideoSubtitleItem } from "./types";

export function useVideoStudio(video: Video, showToast: ShowToast, onUpdated: (video: Video) => void) {
  const { t } = useAppSettings();
  const [title, setTitle] = useState(video.title);
  const [program, setProgram] = useState(video.program || "");
  const [release, setRelease] = useState(video.release || "");
  const [description, setDescription] = useState(video.description || "");
  const [saving, setSaving] = useState(false);
  const [uploadingThumbnail, setUploadingThumbnail] = useState(false);
  const [subtitles, setSubtitles] = useState<VideoSubtitleItem[]>([]);
  const base = `/videos/${video.id}`;

  const fetchSubtitles = async () => {
    try {
      const res = await fetch(getApiUrl(`${base}/subtitles`));
      if (res.ok) {
        const data = await res.json();
        setSubtitles(Array.isArray(data) ? data : []);
      }
    } catch {
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSubtitles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video.id]);

  const saveFailed = async (res: Response) => {
    const errData = await res.json();
    showToast(t("library.saveErrorDetail", { detail: errorMessage(errData, t("library.saveErrorFallback")) }), "error");
  };

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

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch(getApiUrl(base), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          program: program.trim() || null,
          release: release || null,
          description: formatCleanDescription(description) || null,
        }),
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

  const normalize = async () => {
    try {
      const res = await fetch(getApiUrl(`${base}/normalize`), { method: "POST" });
      const data = await res.json();
      if (res.ok) showToast(data.message, "success");
      else showToast(errorMessage(data, t("library.normalizeError")), "error");
    } catch {
      showToast(t("library.normalizeNetworkError"), "error");
    }
  };

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

  return {
    fields: { title, program, release, description },
    setters: { setTitle, setProgram, setRelease, setDescription },
    saving, uploadingThumbnail, subtitles,
    uploadSubtitle, deleteSubtitle, save, normalize, uploadThumbnail,
  };
}

export type VideoStudioState = ReturnType<typeof useVideoStudio>;
