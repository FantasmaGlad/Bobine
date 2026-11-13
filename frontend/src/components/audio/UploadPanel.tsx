"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import { PROGRAMS_LIST_ID } from "./types";
import type { AudioUpload } from "./useAudioUpload";

interface Props {
  upload: AudioUpload;
  onPickFiles: () => void;
  onPickFolder: () => void;
}

function Empty({ upload, onPickFolder }: Omit<Props, "onPickFiles">) {
  const { t } = useAppSettings();
  return (
    <>
      <div className="view-toggle" onClick={(e) => e.stopPropagation()} style={{ marginBottom: "8px" }}>
        <button type="button" className={`view-btn ${upload.mode === "files" ? "active" : ""}`} onClick={() => upload.setMode("files")}>{t("audio.mp3Files")}</button>
        <button type="button" className={`view-btn ${upload.mode === "zip" ? "active" : ""}`} onClick={() => upload.setMode("zip")}>{t("audio.zipArchive")}</button>
      </div>
      <Icon name="cloud_upload" size={48} className="upload-icon" />
      <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: "8px 0 4px" }}>{upload.mode === "files" ? t("audio.dropMp3Hint") : t("audio.dropZipHint")}</h3>
      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0 }}>{t("audio.trackOrderHint")}</p>
      {upload.mode === "files" && (
        <button type="button" className="btn btn-secondary" style={{ marginTop: "12px" }} onClick={(e) => { e.stopPropagation(); onPickFolder(); }}>
          <Icon name="folder_open" size={16} />
          {t("audio.importFolder")}
        </button>
      )}
    </>
  );
}

function Selection({ upload }: { upload: AudioUpload }) {
  const { t } = useAppSettings();
  if (upload.mode === "zip") return <>{t("audio.zipArchiveLabel", { name: upload.zip?.name ?? "" })}</>;
  if (upload.files.length <= 1) return <span>{t("audio.oneTrackSelected")}</span>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontWeight: 700, color: "var(--accent-text)" }}>{t("audio.tracksSelected", { count: upload.files.length })}</span>
      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{t("audio.tracksGrouped", { count: upload.files.length })}</span>
    </div>
  );
}

function Form({ upload }: { upload: AudioUpload }) {
  const { t } = useAppSettings();
  return (
    <div onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: "500px", textAlign: "left" }}>
      <div className="form-group">
        <label className="form-label">{t("audio.courseNameLabel")}</label>
        <input type="text" className="form-control" value={upload.title} onChange={(e) => upload.setTitle(e.target.value)} />
      </div>
      <div style={{ display: "flex", gap: "12px", marginTop: "12px" }}>
        <div className="form-group" style={{ flex: 1, minWidth: 0 }}>
          <label className="form-label">{t("audio.programLabel")}</label>
          <input type="text" list={PROGRAMS_LIST_ID} className="form-control" placeholder={t("audio.programPlaceholder")} value={upload.program} onChange={(e) => upload.setProgram(e.target.value)} />
        </div>
        <div className="form-group" style={{ flex: 1, minWidth: 0 }}>
          <label className="form-label">{t("audio.releaseLabel")}</label>
          <input type="text" className="form-control" placeholder={t("audio.releasePlaceholder")} value={upload.release} onChange={(e) => upload.setRelease(e.target.value)} />
        </div>
      </div>
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: "12px 0" }}><Selection upload={upload} /></div>
      <div style={{ display: "flex", gap: "12px" }}>
        <button type="button" className="btn btn-primary" onClick={upload.submit} style={{ flex: 1, height: "48px" }}>{t("audio.startImport")}</button>
        <button type="button" className="btn btn-secondary" onClick={upload.reset} style={{ height: "48px" }}>{t("common.cancel")}</button>
      </div>
    </div>
  );
}

export default function UploadPanel({ upload, onPickFiles, onPickFolder }: Props) {
  const empty = upload.files.length === 0 && !upload.zip;
  return (
    <div
      className={`upload-zone ${upload.dragActive ? "drag-active" : ""}`}
      onDragEnter={upload.onDrag}
      onDragOver={upload.onDrag}
      onDragLeave={upload.onDrag}
      onDrop={upload.onDrop}
      onClick={() => empty && onPickFiles()}
    >
      {empty ? <Empty upload={upload} onPickFolder={onPickFolder} /> : <Form upload={upload} />}
    </div>
  );
}
