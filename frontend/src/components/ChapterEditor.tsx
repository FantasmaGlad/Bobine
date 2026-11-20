"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { toDraft, useChapterDrafts, useChapterRequests } from "./chapter-editor/chapterDrafts";
import { ChapterActions, ChapterRows } from "./chapter-editor/ChapterParts";

interface ChapterEditorProps {
  videoId: number;
  getApiUrl: (path: string) => string;
  getCurrentTime: () => number;
  onNotify: (message: string, type?: "success" | "error") => void;
}

export default function ChapterEditor({ videoId, getApiUrl, getCurrentTime, onNotify }: ChapterEditorProps) {
  const { t } = useAppSettings();
  const { drafts, setDrafts, dirty, setDirty, edit } = useChapterDrafts(getApiUrl, videoId);
  const { busy, importFile, fromFile, save } = useChapterRequests({ videoId, getApiUrl, onNotify, t, drafts, setDrafts, setDirty });
  const addHere = () => edit((list) => [...list, toDraft({ start_seconds: Math.floor(getCurrentTime()), title: `${t("chapters.toastLabel")} ${list.length + 1}` })]);

  return (
    <div className="chapter-editor">
      <div className="chapter-editor__head">
        <span className="chapter-editor__title">
          <Icon name="format_list_numbered" size={18} />
          {t("chapters.title")}
          {drafts.length > 0 && <span className="chapter-list__count">{drafts.length}</span>}
        </span>
      </div>
      <ChapterActions busy={busy} hasDrafts={drafts.length > 0} exportUrl={getApiUrl(`/videos/${videoId}/chapters/export`)} onImport={importFile} onFromFile={fromFile} onAddHere={addHere} t={t} />
      {drafts.length === 0 ? (
        <p className="chapter-editor__empty">{t("chapters.empty")}</p>
      ) : (
        <ChapterRows
          drafts={drafts}
          onUpdate={(key, patch) => edit((list) => list.map((draft) => (draft.key === key ? { ...draft, ...patch } : draft)))}
          onRemove={(key) => edit((list) => list.filter((item) => item.key !== key))}
          t={t}
        />
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
