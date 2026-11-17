import { useState } from "react";
import { isArchiveName } from "@/lib/mediaFiles";
import type { PendingUploadSpec } from "@/lib/uploads/types";

export function usePendingBackgrounds(addUploads: (specs: PendingUploadSpec[]) => void) {
  const [pendingSpecs, setPendingSpecs] = useState<Array<PendingUploadSpec & { key: string }>>([]);
  const [dragActive, setDragActive] = useState(false);

  const addFiles = (all: File[]) => {
    const archives = all.filter((f) => isArchiveName(f.name));
    if (archives.length > 0) addUploads(archives.map((file) => ({ kind: "background_zip" as const, file, title: file.name })));
    const files = all.filter((f) => !isArchiveName(f.name));
    if (files.length > 0) addPendingSpecs(files);
  };

  const addPendingSpecs = (files: File[]) => {
    const specs = files.map((file) => ({
      key: Math.random().toString(36).slice(2),
      kind: "background" as const,
      file,
      title: file.name.substring(0, file.name.lastIndexOf(".")) || file.name,
    }));
    setPendingSpecs((prev) => [...prev, ...specs]);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length) addFiles(Array.from(e.dataTransfer.files));
  };

  const updatePendingSpec = (key: string, patch: Partial<PendingUploadSpec>) => {
    setPendingSpecs((prev) => prev.map((s) => (s.key === key ? { ...s, ...patch } : s)));
  };

  const removePendingSpec = (key: string) => {
    setPendingSpecs((prev) => prev.filter((s) => s.key !== key));
  };

  const submitPendingUploads = () => {
    if (pendingSpecs.length === 0) return;
    addUploads(pendingSpecs.map(({ file, title }) => ({ kind: "background" as const, file, title })));
    setPendingSpecs([]);
  };

  return { pendingSpecs, clearPendingSpecs: () => setPendingSpecs([]), dragActive, addFiles, handleDrag, handleDrop, updatePendingSpec, removePendingSpec, submitPendingUploads };
}
