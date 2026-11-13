"use client";

import { useRef } from "react";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { ARCHIVE_ACCEPT } from "@/lib/mediaFiles";

import type { RadioImport } from "./useRadioImport";

const STATUS_ICONS: Record<string, string> = { done: "check_circle", error: "error" };

export default function ImportSection({ importer }: { importer: RadioImport }) {
  const { t } = useAppSettings();
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="rl-import-section">
      <div className={`upload-zone ${importer.dragActive ? "drag-active" : ""}`}
        onDragEnter={importer.onDrag} onDragOver={importer.onDrag} onDragLeave={importer.onDrag} onDrop={importer.onDrop}
        onClick={() => importer.pick("files", input.current)}>
        <input ref={input} type="file" accept={`audio/*,${ARCHIVE_ACCEPT}`} multiple style={{ display: "none" }} onChange={(e) => { importer.start(e.target.files); e.target.value = ""; }} />
        <Icon name="cloud_upload" size={44} className="upload-icon" />
        <p style={{ fontSize: "1rem", fontWeight: 800, color: "var(--text-main)", margin: "10px 0 0" }}>{t("radioLibrary.importCta")}</p>
        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: "2px 0 0" }}>{t("radioLibrary.importHint")}</p>
        <button type="button" onClick={(e) => { e.stopPropagation(); importer.pick("folder", input.current); }} className="rl-link-btn">{t("radioLibrary.chooseFolder")}</button>
      </div>
      <h4 className="rl-block-title">{t("radioLibrary.importQueueTitle")}</h4>
      {importer.queue.length === 0 ? (
        <p className="rl-empty-note">{t("radioLibrary.importQueueEmpty")}</p>
      ) : (
        <div className="rl-list">
          {importer.queue.map((u) => (
            <div key={u.id} className="rl-list-row">
              <span className="rl-list-cover"><Icon name={STATUS_ICONS[u.status] ?? "cloud_upload"} size={18} /></span>
              <span className="rl-list-text">
                <span className="rl-list-title">{u.title}</span>
                <span className="rl-list-sub">{u.status === "error" ? (u.error ?? t("radioLibrary.importError")) : t(`radioLibrary.importStatus.${u.status}`)}</span>
              </span>
              <span className="rl-list-duration">{u.status === "done" ? "100 %" : `${u.progress} %`}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
