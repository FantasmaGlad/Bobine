"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { isArchiveName } from "@/lib/mediaFiles";
import { useUploadManager } from "@/lib/UploadManager";

export interface VisualItem {
  id: number;
  file_path: string;
  title: string;
  duration_seconds: number | null;
  thumbnail_path: string | null;
  is_image: boolean;
}

const VISUAL_KINDS = new Set(["visual", "visual_zip"]);

export function useVisualLibrary() {
  const [visuals, setVisuals] = useState<VisualItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  const { uploads, addUploads } = useUploadManager();
  const seen = useRef<Set<string>>(new Set());

  const reload = useCallback(() => fetch(getApiUrl("/visuals"), { cache: "no-store" })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<VisualItem[]>;
    })
    .then((list) => { setVisuals(list); setFailed(false); })
    .catch((error) => { console.warn("Visuels illisibles", error); setFailed(true); }), []);

  useEffect(() => { void reload(); }, [reload]);

  useEffect(() => {
    const done = uploads.filter((u) => VISUAL_KINDS.has(u.kind) && u.status === "done" && !seen.current.has(u.id));
    if (done.length === 0) return;
    done.forEach((u) => seen.current.add(u.id));
    void reload();
  }, [uploads, reload]);

  const importFiles = useCallback((files: File[]) => {
    addUploads(files.map((file) => ({
      kind: isArchiveName(file.name) ? "visual_zip" as const : "visual" as const,
      file,
      title: file.name.substring(0, file.name.lastIndexOf(".")) || file.name,
    })));
  }, [addUploads]);

  const remove = useCallback(async (id: number) => {
    const res = await fetch(getApiUrl(`/visuals/${id}`), { method: "DELETE" }).catch(() => null);
    if (res?.ok) setVisuals((list) => (list ?? []).filter((v) => v.id !== id));
    return !!res?.ok;
  }, []);

  const rename = useCallback(async (id: number, title: string) => {
    const res = await fetch(getApiUrl(`/visuals/${id}`), {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }),
    }).catch(() => null);
    if (!res?.ok) return false;
    const updated = (await res.json()) as VisualItem;
    setVisuals((list) => (list ?? []).map((v) => (v.id === id ? updated : v)));
    return true;
  }, []);

  return { visuals, failed, reload, importFiles, remove, rename };
}
