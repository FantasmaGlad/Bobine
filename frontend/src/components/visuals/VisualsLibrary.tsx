"use client";

import { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMediaDuration } from "@/lib/format";
import { thumbnailUrl } from "@/lib/thumbnail";
import type { ShowToast } from "@/lib/useToast";
import type { VisualItem } from "./useVisualLibrary";

interface Props {
  visuals: VisualItem[] | null;
  failed: boolean;
  onRename: (id: number, title: string) => Promise<boolean>;
  onRemove: (id: number) => Promise<boolean>;
  showToast: ShowToast;
}

function VisualCard({ visual, onRename, onRemove, showToast }: { visual: VisualItem } & Omit<Props, "visuals" | "failed">) {
  const { t } = useAppSettings();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(visual.title);
  const thumb = thumbnailUrl(visual.thumbnail_path);
  const save = async () => {
    if (title.trim() && (await onRename(visual.id, title.trim()))) setEditing(false);
    else showToast(t("visuals.renameError"), "error");
  };
  const remove = async () => {
    if (!window.confirm(t("visuals.deleteConfirm", { title: visual.title }))) return;
    const removed = await onRemove(visual.id);
    showToast(removed ? t("visuals.deleted") : t("visuals.deleteError"), removed ? "success" : "error");
  };
  return (
    <li className="vs-card">
      <span className="vs-thumb">{thumb ? <img src={thumb} alt="" loading="lazy" /> : <Icon name={visual.is_image ? "image" : "movie"} size={28} />}</span>
      <div className="vs-body">
        {editing ? (
          <input className="form-control" value={title} autoFocus aria-label={t("visuals.rename")}
            onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void save(); if (e.key === "Escape") setEditing(false); }} />
        ) : <span className="vs-title">{visual.title}</span>}
        <span className="vs-meta">{visual.is_image ? t("visuals.image") : `${t("visuals.video")} · ${formatMediaDuration(visual.duration_seconds)}`}</span>
      </div>
      <div className="vs-actions">
        {editing
          ? <button type="button" className="btn btn-icon" onClick={() => void save()} title={t("visuals.save")}><Icon name="check" size={18} /></button>
          : <button type="button" className="btn btn-icon" onClick={() => setEditing(true)} title={t("visuals.rename")}><Icon name="edit" size={18} /></button>}
        <button type="button" className="btn btn-icon" onClick={() => void remove()} title={t("visuals.delete")}><Icon name="delete" size={18} /></button>
      </div>
    </li>
  );
}

export default function VisualsLibrary({ visuals, failed, ...actions }: Props) {
  const { t } = useAppSettings();
  if (failed) return <div className="live-empty">{t("visuals.loadError")}</div>;
  if (!visuals) return <div className="live-empty">{t("common.loading")}</div>;
  if (visuals.length === 0) return <div className="live-empty">{t("visuals.empty")}</div>;
  return (
    <ul className="vs-grid">
      {visuals.map((visual) => <VisualCard key={visual.id} visual={visual} {...actions} />)}
    </ul>
  );
}
