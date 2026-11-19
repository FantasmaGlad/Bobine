"use client";

import React from "react";
import Icon from "@/components/Icon";
import { ARCHIVE_ACCEPT } from "@/lib/mediaFiles";
import { AUDIO_ACCEPT, folderOf } from "./files";
import type { useAudioUpload } from "./useAudioUpload";

export default function AudioImportControls({ t, upload, fileInput, bindFolderInput }: {
  t: (key: string) => string;
  upload: ReturnType<typeof useAudioUpload>;
  fileInput: React.RefObject<HTMLInputElement | null>;
  bindFolderInput: (el: HTMLInputElement | null) => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <input ref={fileInput} type="file" accept={upload.mode === "zip" ? ARCHIVE_ACCEPT : AUDIO_ACCEPT} multiple={upload.mode === "files"} style={{ display: "none" }}
        onChange={(e) => { upload.select(e.target.files); e.target.value = ""; }} />
      <input
        ref={bindFolderInput}
        type="file" multiple style={{ display: "none" }}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          upload.select(files, folderOf(files[0]));
          e.target.value = "";
        }}
      />
      <button type="button" className="btn btn-primary" style={{ height: "40px", padding: "0 16px", fontSize: "0.85rem" }} onClick={upload.toggle}>
        <Icon name="cloud_upload" size={18} />
        <span>{t("common.import")}</span>
      </button>
    </div>
  );
}
