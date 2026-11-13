"use client";

import React, { useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { isArchiveName } from "@/lib/mediaFiles";
import { parseMediaName } from "@/lib/parseMediaName";
import { useUploadManager } from "@/lib/UploadManager";
import type { ShowToast } from "@/lib/useToast";

import { collectDroppedAudioFiles, folderOf, guessCourseName, isAudioFile, type CourseName } from "./files";

export type UploadMode = "files" | "zip";

export function useAudioUpload(programs: string[], showToast: ShowToast) {
  const { t } = useAppSettings();
  const { addUploads } = useUploadManager();
  const [mode, setMode] = useState<UploadMode>("files");
  const [files, setFiles] = useState<File[]>([]);
  const [zip, setZip] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [program, setProgram] = useState("");
  const [release, setRelease] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [open, setOpen] = useState(false);

  const adopt = (name: CourseName) => {
    setTitle(name.title);
    if (!program && name.program) setProgram(name.program);
    if (!release && name.release) setRelease(name.release);
  };

  const select = (list: FileList | File[] | null, folderHint?: string | null) => {
    if (!list || list.length === 0) return;
    const all = Array.from(list);
    if (mode === "zip") {
      const archive = all.find((f) => isArchiveName(f.name)) || all[0];
      setZip(archive);
      adopt(parseMediaName(archive.name, programs));
      return;
    }
    const audio = all.filter(isAudioFile);
    setFiles(audio);
    if (audio.length && !title) adopt(guessCourseName(audio, folderHint || folderOf(audio[0]), programs, t("audio.newCourseFallback")));
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
    if (mode === "zip") return select(e.dataTransfer.files);
    collectDroppedAudioFiles(e.dataTransfer).then(({ files: dropped, folderName }) => select(dropped, folderName));
  };

  const reset = () => {
    setFiles([]);
    setZip(null);
    setTitle("");
    setRelease("");
  };

  const missing = (): string | null => {
    if (!title.trim()) return "audio.titleRequiredWarning";
    if (mode === "files" && files.length === 0) return "audio.selectMp3Warning";
    if (mode === "zip" && !zip) return "audio.selectZipWarning";
    return null;
  };

  const submit = () => {
    const warning = missing();
    if (warning) return showToast(t(warning), "warning");
    const common = { title: title.trim(), program, release };
    if (mode === "zip" && zip) addUploads([{ kind: "audio_zip", file: zip, ...common }]);
    else addUploads([{ kind: "audio_files", files, ...common }]);
    reset();
  };

  const visible = open || dragActive || files.length > 0 || zip !== null;

  return { mode, setMode, files, zip, title, setTitle, program, setProgram, release, setRelease, dragActive, visible, toggle: () => setOpen((v) => !v), select, onDrag, onDrop, reset, submit };
}

export type AudioUpload = ReturnType<typeof useAudioUpload>;
