"use client";

import { useRef } from "react";
import Icon from "@/components/Icon";
import { type Draft } from "./chapterDrafts";

type T = (key: string, params?: Record<string, string | number>) => string;

interface ActionsProps {
  busy: boolean;
  hasDrafts: boolean;
  exportUrl: string;
  onImport: (file: File) => void;
  onFromFile: () => void;
  onAddHere: () => void;
  t: T;
}

export function ChapterActions({ busy, hasDrafts, exportUrl, onImport, onFromFile, onAddHere, t }: ActionsProps) {
  const fileInput = useRef<HTMLInputElement | null>(null);
  return (
    <div className="chapter-editor__actions">
      <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => fileInput.current?.click()}>
        <Icon name="upload_file" size={16} />
        {t("chapters.import")}
      </button>
      <button type="button" className="btn btn-secondary" disabled={busy} onClick={onFromFile}>
        <Icon name="movie" size={16} />
        {t("chapters.fromFile")}
      </button>
      <button type="button" className="btn btn-secondary" disabled={busy} onClick={onAddHere}>
        <Icon name="add" size={16} />
        {t("chapters.addHere")}
      </button>
      {hasDrafts && (
        <a className="btn btn-secondary" href={exportUrl} download>
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
          if (file) onImport(file);
          event.target.value = "";
        }}
      />
    </div>
  );
}

interface RowsProps {
  drafts: Draft[];
  onUpdate: (key: number, patch: Partial<Draft>) => void;
  onRemove: (key: number) => void;
  t: T;
}

export function ChapterRows({ drafts, onUpdate, onRemove, t }: RowsProps) {
  return (
    <ol className="chapter-editor__rows">
      {drafts.map((draft) => (
        <li key={draft.key} className="chapter-editor__row">
          <input
            className="form-control chapter-editor__time"
            value={draft.start}
            inputMode="numeric"
            aria-label={t("chapters.title")}
            onChange={(event) => onUpdate(draft.key, { start: event.target.value })}
          />
          <input
            className="form-control chapter-editor__name"
            value={draft.title}
            placeholder={t("chapters.titlePlaceholder")}
            onChange={(event) => onUpdate(draft.key, { title: event.target.value })}
          />
          <button
            type="button"
            className="chapter-editor__remove olc-press"
            title={t("chapters.remove")}
            aria-label={t("chapters.remove")}
            onClick={() => onRemove(draft.key)}
          >
            <Icon name="close" size={18} />
          </button>
        </li>
      ))}
    </ol>
  );
}
