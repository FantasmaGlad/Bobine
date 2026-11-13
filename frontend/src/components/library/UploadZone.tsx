"use client";

import React from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { PendingUploadSpec } from "@/lib/UploadManager";

import PendingSpecCard from "./PendingSpecCard";
import type { PendingSpec } from "./types";

interface Props {
  dragActive: boolean;
  specs: PendingSpec[];
  onDrag: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onPick: () => void;
  onUpdate: (key: string, patch: Partial<PendingUploadSpec>) => void;
  onRemove: (key: string) => void;
  onSubmit: () => void;
  onClear: () => void;
}

function DropHint() {
  const { t } = useAppSettings();
  return (
    <>
      <Icon name="cloud_upload" size={48} className="upload-icon" />
      <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: "8px 0 4px" }}>{t("library.uploadDropHint")}</h3>
      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>{t("library.uploadFormatsHint")}</p>
      <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "4px" }}>{t("library.multipleFilesHint")}</p>
    </>
  );
}

function PendingList({ specs, onPick, onUpdate, onRemove, onSubmit, onClear }: Omit<Props, "dragActive" | "onDrag" | "onDrop">) {
  const { t } = useAppSettings();
  return (
    <div onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: "680px", textAlign: "left" }}>
      <h3 style={{ fontSize: "1.05rem", fontWeight: 800, marginBottom: "12px", color: "var(--accent-text)", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px" }}>
        {t(specs.length > 1 ? "library.filesSelectedMany" : "library.filesSelectedOne", { count: specs.length })}
      </h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxHeight: "380px", overflowY: "auto", paddingRight: "4px" }}>
        {specs.map((spec) => (
          <PendingSpecCard key={spec.key} spec={spec} onUpdate={(patch) => onUpdate(spec.key, patch)} onRemove={() => onRemove(spec.key)} />
        ))}
      </div>
      <div style={{ display: "flex", gap: "12px", marginTop: "14px" }}>
        <button type="button" className="btn btn-primary" onClick={onSubmit} style={{ flex: 1, height: "44px" }}>
          {t(specs.length > 1 ? "library.startUploadsMany" : "library.startUploadsOne", { count: specs.length })}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onClear} style={{ height: "44px" }}>
          {t("common.cancel")}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onPick} style={{ height: "44px", whiteSpace: "nowrap" }}>
          + {t("common.add")}
        </button>
      </div>
    </div>
  );
}

export default function UploadZone(props: Props) {
  const { dragActive, specs, onDrag, onDrop, onPick } = props;
  return (
    <div
      className={`upload-zone ${dragActive ? "drag-active" : ""}`}
      onDragEnter={onDrag}
      onDragOver={onDrag}
      onDragLeave={onDrag}
      onDrop={onDrop}
      onClick={() => {
        if (specs.length === 0) onPick();
      }}
    >
      {specs.length === 0 ? <DropHint /> : <PendingList {...props} />}
    </div>
  );
}
