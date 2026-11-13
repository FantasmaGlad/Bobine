"use client";

import React, { useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { hasExtension, isArchiveName, RADIO_AUDIO_EXTENSIONS } from "@/lib/mediaFiles";
import { useUploadManager } from "@/lib/UploadManager";
import type { ShowToast } from "@/lib/useToast";

type Mode = "files" | "folder";

const isAudioFile = (name: string) => hasExtension(name, RADIO_AUDIO_EXTENSIONS);

export function useRadioImport(showToast: ShowToast) {
  const { t } = useAppSettings();
  const { uploads, addUploads } = useUploadManager();
  const [mode, setMode] = useState<Mode>("files");
  const [dragActive, setDragActive] = useState(false);
  const queue = uploads.filter((u) => u.kind === "radio_files" || u.kind === "radio_zip").slice(-12).reverse();

  const pick = (next: Mode, el: HTMLInputElement | null) => {
    setMode(next);
    if (!el) return;
    if (next === "folder") {
      el.setAttribute("webkitdirectory", "");
      el.setAttribute("directory", "");
    } else {
      el.removeAttribute("webkitdirectory");
      el.removeAttribute("directory");
    }
    el.click();
  };

  const start = (fileList: FileList | null, override?: Mode) => {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    const audio = (override ?? mode) === "folder" ? files.filter((f) => isAudioFile(f.name)) : files;
    if (audio.length === 0) {
      showToast(t("radioLibrary.noAudioInFolder"), "warning");
      return;
    }
    if ((override ?? mode) !== "folder" && audio.length === 1 && isArchiveName(audio[0].name)) {
      addUploads([{ kind: "radio_zip", file: audio[0], title: audio[0].name }]);
    } else {
      addUploads(audio.map((f) => ({ kind: "radio_files" as const, files: [f], title: f.name })));
    }
    showToast(t("radioLibrary.importStarted"));
  };

  const onDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    start(e.dataTransfer.files, "files");
  };

  return { queue, dragActive, pick, start, onDrag, onDrop };
}

export type RadioImport = ReturnType<typeof useRadioImport>;
