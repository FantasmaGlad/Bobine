"use client";

import React, { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMediaDuration } from "@/lib/format";
import type { Announcement } from "./types";

interface AnnouncementItemProps {
  announcement: Announcement;
  editing: boolean;
  onEdit: (id: number | null) => void;
  onSave: (id: number, value: string) => Promise<boolean>;
  onToggle: (a: Announcement) => void;
  onPlay: (id: number) => void;
  onAskDelete: (id: number) => void;
}

export default function AnnouncementItem({ announcement: a, editing, onEdit, onSave, onToggle, onPlay, onAskDelete }: AnnouncementItemProps) {
  const { t } = useAppSettings();
  const [editValue, setEditValue] = useState(a.description);
  const save = async () => {
    if (await onSave(a.id, editValue)) onEdit(null);
  };
  const startEdit = () => {
    setEditValue(a.description);
    onEdit(a.id);
  };
  return (
    <div className={`ra-item ${a.enabled ? "" : "off"}`}>
      <button className="ra-item-play" onClick={() => onPlay(a.id)} disabled={!a.enabled} title={t("radioAnnouncements.playNow")}>
        <Icon name="play_arrow" size={18} filled />
      </button>
      <div className="ra-item-body">
        {editing ? (
          <input
            type="text"
            className="form-control"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") save(); }}
            autoFocus
          />
        ) : (
          <>
            <span className="ra-item-desc">{a.description}</span>
            <span className="ra-item-dur">{formatMediaDuration(a.duration_seconds)}</span>
          </>
        )}
      </div>
      <label className="ra-switch" title={t("radioAnnouncements.enabledLabel")}>
        <input type="checkbox" checked={a.enabled} onChange={() => onToggle(a)} />
        <span className="ra-switch-track" />
      </label>
      {editing ? (
        <div className="ra-item-actions">
          <button className="btn btn-primary ra-icon-btn" onClick={save} title={t("radioAnnouncements.save")}><Icon name="check" size={16} /></button>
          <button className="btn btn-secondary ra-icon-btn" onClick={() => onEdit(null)} title={t("radioAnnouncements.cancel")}><Icon name="close" size={16} /></button>
        </div>
      ) : (
        <div className="ra-item-actions">
          <button className="btn btn-secondary ra-icon-btn" onClick={startEdit} title={t("radioAnnouncements.edit")}><Icon name="edit" size={16} /></button>
          <button className="btn btn-danger ra-icon-btn" onClick={() => onAskDelete(a.id)} title={t("radioAnnouncements.delete")}><Icon name="delete" size={16} /></button>
        </div>
      )}
    </div>
  );
}
