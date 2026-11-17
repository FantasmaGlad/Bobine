"use client";

import React, { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import AnnouncementItem from "./AnnouncementItem";
import type { Announcement } from "./types";

interface AnnouncementListProps {
  announcements: Announcement[];
  loading: boolean;
  onSave: (id: number, value: string) => Promise<boolean>;
  onToggle: (a: Announcement) => void;
  onPlay: (id: number) => void;
  onAskDelete: (id: number) => void;
}

export default function AnnouncementList({ announcements, loading, ...handlers }: AnnouncementListProps) {
  const { t } = useAppSettings();
  const [editingId, setEditingId] = useState<number | null>(null);
  return (
    <div className="ra-card">
      <h3 className="ra-card-title">
        <Icon name="record_voice_over" size={18} /> {t("radioAnnouncements.listTitle")}
        {announcements.length > 0 && <span className="ra-count">{announcements.length}</span>}
      </h3>
      {loading ? (
        <p className="live-empty">{t("radioAnnouncements.loading")}</p>
      ) : announcements.length === 0 ? (
        <div className="ra-empty">
          <Icon name="campaign" size={36} style={{ opacity: 0.25 }} />
          <p>{t("radioAnnouncements.empty")}</p>
        </div>
      ) : (
        <div className="ra-list">
          {announcements.map((a) => (
            <AnnouncementItem key={a.id} announcement={a} editing={editingId === a.id} onEdit={setEditingId} {...handlers} />
          ))}
        </div>
      )}
    </div>
  );
}
