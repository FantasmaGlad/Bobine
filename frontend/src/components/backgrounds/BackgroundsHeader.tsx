"use client";

import React from "react";
import Icon from "@/components/Icon";
import { ARCHIVE_ACCEPT, VIDEO_ACCEPT } from "@/lib/mediaFiles";

export default function BackgroundsHeader({ t, fileInputRef, addFiles }: {
  t: (key: string) => string;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  addFiles: (files: File[]) => void;
}) {
  return (
    <div className="library-header-bar" style={{ marginBottom: "8px" }}>
      <div>
        <h1 style={{ fontFamily: "var(--font-title)", fontSize: "1.5rem", fontWeight: 900, margin: "0 0 4px" }}>
          {t("backgrounds.hubTitle")}
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", margin: 0, maxWidth: "680px" }}>
          {t("backgrounds.hubSubtitle")}
        </p>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <input
          ref={fileInputRef}
          type="file"
          accept={`${VIDEO_ACCEPT},image/*,${ARCHIVE_ACCEPT}`}
          multiple
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files?.length) addFiles(Array.from(e.target.files));
            e.target.value = "";
          }}
        />
        <button
          type="button"
          className="btn btn-primary"
          style={{ height: "40px", padding: "0 16px", fontSize: "0.85rem" }}
          onClick={() => fileInputRef.current?.click()}
        >
          <Icon name="cloud_upload" size={18} />
          <span>{t("common.import")}</span>
        </button>
      </div>
    </div>
  );
}
