"use client";
import React from "react";
import Icon from "@/components/Icon";
import type { PendingUploadSpec } from "@/lib/UploadManager";

interface PendingBackgroundsProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  dragActive: boolean;
  pendingSpecs: Array<PendingUploadSpec & { key: string }>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleDrag: (e: React.DragEvent) => void;
  handleDrop: (e: React.DragEvent) => void;
  updatePendingSpec: (key: string, patch: Partial<PendingUploadSpec>) => void;
  removePendingSpec: (key: string) => void;
  submitPendingUploads: () => void;
  clearPendingSpecs: () => void;
}

export default function PendingBackgrounds({
  t, dragActive, pendingSpecs, fileInputRef, handleDrag, handleDrop, updatePendingSpec, removePendingSpec, submitPendingUploads, clearPendingSpecs,
}: PendingBackgroundsProps) {
  return (
      <div
        className={`upload-zone ${dragActive ? "drag-active" : ""}`}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => {
          if (pendingSpecs.length === 0 && fileInputRef.current) fileInputRef.current.click();
        }}
      >
        {pendingSpecs.length === 0 ? (
          <>
            <Icon name="cloud_upload" size={48} className="upload-icon" />
            <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: "8px 0 4px" }}>
              {t("backgrounds.dropHint")}
            </h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>
              {t("backgrounds.formatsHint")}
            </p>
          </>
        ) : (
          <div onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: "560px", textAlign: "left" }}>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "12px", color: "var(--accent-text)", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px" }}>
              {t(pendingSpecs.length > 1 ? "backgrounds.filesSelectedMany" : "backgrounds.filesSelectedOne", { count: pendingSpecs.length })}
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "320px", overflowY: "auto", paddingRight: "4px" }}>
              {pendingSpecs.map((spec) => (
                <div key={spec.key} style={{ background: "var(--bg-surface-hover)", borderRadius: "8px", padding: "10px 12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={spec.file?.name}>
                      {spec.file?.name} ({((spec.file?.size ?? 0) / (1024 * 1024)).toFixed(1)} Mo)
                    </span>
                    <button aria-label={t("common.remove")} onClick={() => removePendingSpec(spec.key)} className="olc-press" style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", flexShrink: 0, display: "flex" }}>
                      <Icon name="close" size={16} />
                    </button>
                  </div>
                  <input
                    type="text"
                    className="form-control"
                    placeholder={t("backgrounds.nameLabel")}
                    value={spec.title}
                    onChange={(e) => updatePendingSpec(spec.key, { title: e.target.value })}
                    style={{ padding: "6px 10px", fontSize: "0.85rem" }}
                  />
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: "12px", marginTop: "14px" }}>
              <button type="button" className="btn btn-primary" onClick={submitPendingUploads} style={{ flex: 1, height: "44px" }}>
                {t("backgrounds.startImport")} ({pendingSpecs.length})
              </button>
              <button type="button" className="btn btn-secondary" onClick={clearPendingSpecs} style={{ height: "44px" }}>
                {t("common.cancel")}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => fileInputRef.current?.click()} style={{ height: "44px", whiteSpace: "nowrap" }}>
                + {t("common.add")}
              </button>
            </div>
          </div>
        )}
      </div>
  );
}
