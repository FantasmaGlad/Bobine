"use client";

import React from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";

interface DeleteAnnouncementDialogProps {
  description: string;
  onCancel: () => void;
  onConfirm: () => void;
}

export default function DeleteAnnouncementDialog({ description, onCancel, onConfirm }: DeleteAnnouncementDialogProps) {
  const { t } = useAppSettings();
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "420px" }}>
        <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0 }}>{t("radioAnnouncements.deleteConfirmTitle")}</h3>
        <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
          {t("radioAnnouncements.deleteConfirmText", { description })}
        </p>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onCancel}>{t("radioAnnouncements.cancel")}</button>
          <button className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={onConfirm}>{t("radioAnnouncements.confirmDelete")}</button>
        </div>
      </div>
    </div>
  );
}
