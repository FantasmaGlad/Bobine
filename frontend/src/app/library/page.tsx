"use client";

import { useRef, useState } from "react";

import Icon from "@/components/Icon";
import LibraryMedia from "@/components/library/LibraryMedia";
import { useLibraryUploads } from "@/components/library/useLibraryUploads";
import PageNav from "@/components/PageNav";
import VideoPlaylistManager from "@/components/library/VideoPlaylistManager";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { ARCHIVE_ACCEPT, VIDEO_ACCEPT } from "@/lib/mediaFiles";
import { useToast } from "@/lib/useToast";

export default function LibraryPage() {
  const { t } = useAppSettings();
  const [mode, setMode] = useState<"media" | "playlists">("media");
  const fileInput = useRef<HTMLInputElement>(null);
  const programs = useRef<string[]>([]);
  const { toast, showToast } = useToast();
  const uploads = useLibraryUploads(() => programs.current, showToast);
  const media = mode === "media";
  const pick = () => fileInput.current?.click();

  return (
    <div
      className={`library-container ${media ? "" : "playlists-mode"}`}
      onDragEnter={media ? uploads.onDrag : undefined}
      onDragOver={media ? uploads.onDrag : undefined}
      onDragLeave={media ? uploads.onDrag : undefined}
      onDrop={media ? uploads.onDrop : undefined}
    >
      <PageNav
        tabs={[{ id: "media", icon: "video_library", label: t("library.mediaTab") }, { id: "playlists", icon: "playlist_play", label: t("library.playlistsTab") }]}
        value={mode}
        onChange={(id) => setMode(id as typeof mode)}
        ariaLabel={t("library.mediaTab")}
        actions={<>{media && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <input ref={fileInput} type="file" accept={`${VIDEO_ACCEPT},${ARCHIVE_ACCEPT}`} multiple style={{ display: "none" }} onChange={uploads.onFileChange} />
            <button type="button" className="btn btn-primary" style={{ height: "40px", padding: "0 16px", fontSize: "0.85rem" }} onClick={pick}>
              <Icon name="cloud_upload" size={18} />
              <span>{t("common.import")}</span>
            </button>
          </div>
        )}</>}
      />
      {media ? <LibraryMedia uploads={uploads} onPick={pick} toast={toast} showToast={showToast} programsRef={programs} /> : <VideoPlaylistManager />}
    </div>
  );
}
