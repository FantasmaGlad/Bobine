"use client";

import React, { useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatCleanDescription } from "@/lib/formatDescription";
import { isArchiveName, partitionVideoFiles } from "@/lib/mediaFiles";
import { parseMediaName } from "@/lib/parseMediaName";
import { useUploadManager, type PendingUploadSpec } from "@/lib/UploadManager";
import type { ShowToast } from "@/lib/useToast";

import type { PendingSpec } from "./types";

function specsFor(files: File[], subtitles: File[], programs: string[]): PendingSpec[] {
  return files.map((file) => {
    const { title, program, release } = parseMediaName(file.name, programs);
    const baseStem = file.name.substring(0, file.name.lastIndexOf(".")).toLowerCase();
    const matched = subtitles.filter((sub) => sub.name.toLowerCase().startsWith(baseStem) || files.length === 1);
    return { key: Math.random().toString(36).slice(2), kind: "video" as const, file, title, program, release, description: "", subtitles: matched };
  });
}

export function useLibraryUploads(programs: () => string[], showToast: ShowToast) {
  const { t } = useAppSettings();
  const { addUploads } = useUploadManager();
  const [specs, setSpecs] = useState<PendingSpec[]>([]);
  const [dragActive, setDragActive] = useState(false);

  const attachSubtitles = (subtitles: File[]) => {
    setSpecs((prev) => {
      if (prev.length === 0) {
        showToast(t("library.subtitleNeedsVideo"), "warning");
        return prev;
      }
      const [first, ...rest] = prev;
      return [{ ...first, subtitles: [...(first.subtitles ?? []), ...subtitles] }, ...rest];
    });
    showToast(t("library.subtitlesAttached", { count: subtitles.length }), "success");
  };

  const accept = (all: File[]) => {
    const archives = all.filter((f) => isArchiveName(f.name));
    if (archives.length > 0) addUploads(archives.map((file) => ({ kind: "video_zip" as const, file, title: file.name })));
    const { accepted, subtitles, rejected } = partitionVideoFiles(all.filter((f) => !isArchiveName(f.name)));
    if (accepted.length > 0) setSpecs((prev) => [...prev, ...specsFor(accepted, subtitles, programs())]);
    else if (subtitles.length > 0) attachSubtitles(subtitles);
    if (rejected.length > 0) {
      const names = rejected.slice(0, 3).map((f) => f.name).join(", ") + (rejected.length > 3 ? "…" : "");
      showToast(t("library.unsupportedFiles", { count: rejected.length, names }), "warning");
    }
  };

  const onDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    accept(Array.from(e.dataTransfer.files));
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) accept(files);
    e.target.value = "";
  };

  const update = (key: string, patch: Partial<PendingUploadSpec>) => setSpecs((prev) => prev.map((s) => (s.key === key ? { ...s, ...patch } : s)));
  const remove = (key: string) => setSpecs((prev) => prev.filter((s) => s.key !== key));

  const submit = () => {
    if (specs.length === 0) return;
    addUploads(specs.map(({ file, title, program, release, description, subtitles }) => ({
      kind: "video" as const, file, title, program, release, description: formatCleanDescription(description) || undefined, subtitles,
    })));
    setSpecs([]);
  };

  return { specs, dragActive, onDrag, onDrop, onFileChange, update, remove, submit, clear: () => setSpecs([]) };
}
