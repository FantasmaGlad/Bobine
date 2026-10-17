"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { Chapter } from "@/lib/chapters";
import { formatClock, parseClock } from "@/lib/courseMeta";

interface Draft {
  key: number;
  start: string;
  title: string;
}

interface ChapterEditorProps {
  videoId: number;
  getApiUrl: (path: string) => string;
  /** Position du lecteur de l'aperçu, pour « Ajouter ici ». */
  getCurrentTime: () => number;
  onNotify: (message: string, type?: "success" | "error") => void;
}

let draftKey = 0;
const toDraft = (chapter: Pick<Chapter, "start_seconds" | "title">): Draft => ({
  key: ++draftKey,
  start: formatClock(chapter.start_seconds),
  title: chapter.title,
});

/** Édition des chapitres d'un cours : import, lecture dans le fichier vidéo, ajout à la position du lecteur, export. */
export default function ChapterEditor({ videoId, getApiUrl, getCurrentTime, onNotify }: ChapterEditorProps) {
  const { t } = useAppSettings();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);

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
        onNotify(detail?.detail ?? t("chapters.error"), "error");
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
    void apply(
      fetch(getApiUrl(`/videos/${videoId}/chapters`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapters }),
      }),
    );
  };

  const update = (key: number, patch: Partial<Draft>) => {
    setDrafts((list) => list.map((draft) => (draft.key === key ? { ...draft, ...patch } : draft)));
    setDirty(true);
  };

  return (
    <div className="chapter-editor">
      <div className="chapter-editor__head">
        <span className="chapter-editor__title">
          <Icon name="format_list_numbered" size={18} />
          {t("chapters.title")}
          {drafts.length > 0 && <span className="chapter-list__count">{drafts.length}</span>}
        </span>
      </div>

      <div className="chapter-editor__actions">
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => fileInput.current?.click()}>
          <Icon name="upload_file" size={16} />
          {t("chapters.import")}
        </button>
        <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void apply(fetch(getApiUrl(`/videos/${videoId}/chapters/from-file`), { method: "POST" }))}>
          <Icon name="movie" size={16} />
          {t("chapters.fromFile")}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          onClick={() => {
            setDrafts((list) => [...list, toDraft({ start_seconds: Math.floor(getCurrentTime()), title: `${t("chapters.toastLabel")} ${list.length + 1}` })]);
            setDirty(true);
          }}
        >
          <Icon name="add" size={16} />
          {t("chapters.addHere")}
        </button>
        {drafts.length > 0 && (
          <a className="btn btn-secondary" href={getApiUrl(`/videos/${videoId}/chapters/export`)} download>
            <Icon name="download" size={16} />
            {t("chapters.export")}
          </a>
        )}
        <input
          ref={fileInput}
          type="file"
          accept=".json,.vtt,.txt,application/json,text/vtt,text/plain"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) importFile(file);
            event.target.value = "";
          }}
        />
      </div>

      {drafts.length === 0 ? (
        <p className="chapter-editor__empty">{t("chapters.empty")}</p>
      ) : (
        <ol className="chapter-editor__rows">
          {drafts.map((draft) => (
            <li key={draft.key} className="chapter-editor__row">
              <input
                className="form-control chapter-editor__time"
                value={draft.start}
                inputMode="numeric"
                aria-label={t("chapters.title")}
                onChange={(event) => update(draft.key, { start: event.target.value })}
              />
              <input
                className="form-control chapter-editor__name"
                value={draft.title}
                placeholder={t("chapters.titlePlaceholder")}
                onChange={(event) => update(draft.key, { title: event.target.value })}
              />
              <button
                type="button"
                className="chapter-editor__remove olc-press"
                title={t("chapters.remove")}
                aria-label={t("chapters.remove")}
                onClick={() => {
                  setDrafts((list) => list.filter((item) => item.key !== draft.key));
                  setDirty(true);
                }}
              >
                <Icon name="close" size={18} />
              </button>
            </li>
          ))}
        </ol>
      )}
      <p className="chapter-editor__hint">{t("chapters.importHint")}</p>
      {dirty && (
        <button type="button" className="btn btn-primary" disabled={busy} onClick={save}>
          {t("chapters.save")}
        </button>
      )}
    </div>
  );
}
