import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "@/lib/apiError";
import type { Chapter } from "@/lib/chapters";
import { formatClock, parseClock } from "@/lib/courseMeta";

export interface Draft {
  key: number;
  start: string;
  title: string;
}

type T = (key: string, params?: Record<string, string | number>) => string;
type Notify = (message: string, type?: "success" | "error") => void;

let draftKey = 0;
export const toDraft = (chapter: Pick<Chapter, "start_seconds" | "title">): Draft => ({
  key: ++draftKey,
  start: formatClock(chapter.start_seconds),
  title: chapter.title,
});

export function useChapterDrafts(getApiUrl: (path: string) => string, videoId: number) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(() => {
    fetch(getApiUrl(`/videos/${videoId}/chapters`))
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Chapter[]) => {
        setDrafts(Array.isArray(data) ? data.map(toDraft) : []);
        setDirty(false);
      })
      .catch(() => setDrafts([]));
  }, [getApiUrl, videoId]);

  useEffect(load, [load]);

  const edit = (change: (list: Draft[]) => Draft[]) => {
    setDrafts(change);
    setDirty(true);
  };
  return { drafts, setDrafts, dirty, setDirty, edit };
}

interface Requests {
  videoId: number;
  getApiUrl: (path: string) => string;
  onNotify: Notify;
  t: T;
  drafts: Draft[];
  setDrafts: (drafts: Draft[]) => void;
  setDirty: (dirty: boolean) => void;
}

export function useChapterRequests({ videoId, getApiUrl, onNotify, t, drafts, setDrafts, setDirty }: Requests) {
  const [busy, setBusy] = useState(false);
  const apply = async (request: Promise<Response>) => {
    setBusy(true);
    try {
      const res = await request;
      if (res.ok) {
        const data: Chapter[] = await res.json();
        setDrafts(data.map(toDraft));
        setDirty(false);
        onNotify(t("chapters.saved"), "success");
      } else {
        const detail = await res.json().catch(() => null);
        onNotify(errorMessage(detail, t("chapters.error")), "error");
      }
    } catch {
      onNotify(t("chapters.error"), "error");
    } finally {
      setBusy(false);
    }
  };
  const importFile = (file: File) => {
    const form = new FormData();
    form.append("file", file);
    void apply(fetch(getApiUrl(`/videos/${videoId}/chapters/import`), { method: "POST", body: form }));
  };
  const fromFile = () => void apply(fetch(getApiUrl(`/videos/${videoId}/chapters/from-file`), { method: "POST" }));
  const save = () => {
    const chapters: { start_seconds: number; title: string }[] = [];
    for (const draft of drafts) {
      const start = parseClock(draft.start);
      if (start === null) {
        onNotify(`${t("chapters.error")} : « ${draft.start} »`, "error");
        return;
      }
      chapters.push({ start_seconds: start, title: draft.title });
    }
    void apply(fetch(getApiUrl(`/videos/${videoId}/chapters`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapters }),
    }));
  };
  return { busy, importFile, fromFile, save };
}
