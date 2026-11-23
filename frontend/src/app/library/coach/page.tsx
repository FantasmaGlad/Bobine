"use client";

import { useRef } from "react";

import AudioImportControls from "@/components/audio/AudioImportControls";
import AudioPlaylistManager from "@/components/audio/AudioPlaylistManager";
import CoachCoursesView from "@/components/audio/CoachCoursesView";
import { useAudioCourses } from "@/components/audio/useAudioCourses";
import { useAudioUpload } from "@/components/audio/useAudioUpload";
import BackgroundsLibrary from "@/components/backgrounds/BackgroundsLibrary";
import PageNav from "@/components/PageNav";
import { oneOf } from "@/lib/urlView";
import { useUrlView } from "@/lib/useUrlView";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useToast } from "@/lib/useToast";

const COACH_VIEWS = oneOf(["courses", "playlists", "backgrounds"] as const, "courses");

export default function CoachLibraryPage() {
  const { t } = useAppSettings();
  const [mode, setMode] = useUrlView("vue", COACH_VIEWS);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement | null>(null);
  const { toast, showToast } = useToast();
  const courses = useAudioCourses(showToast);
  const upload = useAudioUpload(courses.programs, showToast);
  const isCourses = mode === "courses";
  const bindFolderInput = (el: HTMLInputElement | null) => {
    folderInput.current = el;
    el?.setAttribute("webkitdirectory", "");
    el?.setAttribute("directory", "");
  };

  return (
    <div
      className={`library-container ${mode === "playlists" ? "playlists-mode" : ""}`}
      onDragEnter={isCourses ? upload.onDrag : undefined}
      onDragOver={isCourses ? upload.onDrag : undefined}
      onDragLeave={isCourses ? upload.onDrag : undefined}
      onDrop={isCourses ? upload.onDrop : undefined}
    >
      <PageNav
        tabs={[
          { id: "courses", icon: "library_music", label: t("audio.coursesTab") },
          { id: "playlists", icon: "playlist_play", label: t("audio.playlistsTab") },
          { id: "backgrounds", icon: "gradient", label: t("audio.backgroundsTab") },
        ]}
        value={mode}
        onChange={(id) => setMode(id as typeof mode)}
        ariaLabel={t("audio.coursesTab")}
        actions={<>{isCourses && <AudioImportControls t={t} upload={upload} fileInput={fileInput} bindFolderInput={bindFolderInput} />}</>}
      />
      {mode === "backgrounds" && <BackgroundsLibrary />}
      {mode === "playlists" && <AudioPlaylistManager />}
      {isCourses && (
        <CoachCoursesView courses={courses} upload={upload} toast={toast} showToast={showToast}
          onPickFiles={() => fileInput.current?.click()} onPickFolder={() => folderInput.current?.click()} />
      )}
    </div>
  );
}
