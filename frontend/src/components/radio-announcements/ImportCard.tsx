"use client";

import React, { type RefObject } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { AnnouncementImport } from "./useAnnouncementImport";

const FOLDER_LINK: React.CSSProperties = {
  marginTop: "10px", background: "none", border: "none", padding: 0,
  color: "var(--accent-text)", fontWeight: 700, fontSize: "0.8rem",
  cursor: "pointer", textDecoration: "underline",
};

type FileInput = RefObject<HTMLInputElement | null>;

function DropZone({ io, fileInputRef }: { io: AnnouncementImport; fileInputRef: FileInput }) {
  const { t } = useAppSettings();
  return (
    <div
      className={`upload-zone ${io.dragActive ? "drag-active" : ""}`}
      onDragEnter={io.handleDrag} onDragOver={io.handleDrag} onDragLeave={io.handleDrag} onDrop={io.handleDrop}
      onClick={() => io.openPicker(false)}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*"
        style={{ display: "none" }}
        onChange={(e) => (io.uploadMode === "folder" ? io.uploadFolder(e.target.files) : io.setSelectedFileName(e.target.files?.[0]?.name ?? ""))}
      />
      <Icon name="cloud_upload" size={36} className="upload-icon" />
      <p style={{ fontSize: "1rem", fontWeight: 800, color: "var(--text-main)", margin: "8px 0 0" }}>{t("radioAnnouncements.importCta")}</p>
      <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: "2px 0 0" }}>{t("radioAnnouncements.dropFileHint")}</p>
      {io.selectedFileName && (
        <p style={{ fontSize: "0.8rem", fontWeight: 700, margin: "4px 0 0", color: "var(--accent-text)" }}>{io.selectedFileName}</p>
      )}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          io.openPicker(true);
        }}
        style={FOLDER_LINK}
      >
        {t("radioAnnouncements.chooseFolder")}
      </button>
    </div>
  );
}

export default function ImportCard({ io, fileInputRef }: { io: AnnouncementImport; fileInputRef: FileInput }) {
  const { t } = useAppSettings();
  return (
    <div className="ra-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <h3 className="ra-card-title" style={{ margin: 0 }}>
          <Icon name="upload" size={18} /> {t("radioAnnouncements.importTitle")}
        </h3>
        <button aria-label={t("common.close")} type="button" className="close-btn" style={{ padding: "4px" }} onClick={io.close}>
          <Icon name="close" size={18} />
        </button>
      </div>
      <DropZone io={io} fileInputRef={fileInputRef} />
      {io.uploadMode === "file" && (
        <div className="ra-import-form" style={{ marginTop: "10px" }}>
          <label className="ra-field">
            <span className="ra-field-label">{t("radioAnnouncements.descriptionLabel")}</span>
            <input
              type="text"
              className="form-control"
              placeholder={t("radioAnnouncements.descriptionPlaceholder")}
              value={io.description}
              onChange={(e) => io.setDescription(e.target.value)}
            />
          </label>
          <button className="btn btn-primary" style={{ height: "44px" }} onClick={io.uploadFile} disabled={io.uploading || !io.description.trim()}>
            <Icon name="upload" size={16} /> {io.uploading ? t("radioAnnouncements.importing") : t("radioAnnouncements.importButton")}
          </button>
        </div>
      )}
    </div>
  );
}
