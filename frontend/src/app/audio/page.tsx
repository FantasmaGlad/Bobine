"use client";

import { useRef, useState } from "react";

import AudioPlaylistManager from "@/components/audio/AudioPlaylistManager";
import BackgroundPicker from "@/components/audio/BackgroundPicker";
import CourseDrawer from "@/components/audio/CourseDrawer";
import CourseGrid from "@/components/audio/CourseGrid";
import { AUDIO_ACCEPT, folderOf } from "@/components/audio/files";
import { PROGRAMS_LIST_ID } from "@/components/audio/types";
import UploadPanel from "@/components/audio/UploadPanel";
import { useAudioCourses } from "@/components/audio/useAudioCourses";
import { useAudioUpload } from "@/components/audio/useAudioUpload";
import { useCourseEditor } from "@/components/audio/useCourseEditor";
import ConfirmDialog from "@/components/ConfirmDialog";
import Icon from "@/components/Icon";
import PageNav from "@/components/PageNav";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { ARCHIVE_ACCEPT } from "@/lib/mediaFiles";
import { useToast } from "@/lib/useToast";

type Picker = { trackId: number | null } | null;

export default function AudioLibraryPage() {
  const { t } = useAppSettings();
  const [mode, setMode] = useState<"courses" | "playlists">("courses");
  const [picker, setPicker] = useState<Picker>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement | null>(null);
  const { toast, showToast } = useToast();
  const courses = useAudioCourses(showToast);
  const upload = useAudioUpload(courses.programs, showToast);
  const editor = useCourseEditor(courses, showToast);
  const isCourses = mode === "courses";
  const course = editor.course;

  const pickerSelected = picker?.trackId
    ? course?.tracks.find((tr) => tr.id === picker.trackId)?.background_id ?? null
    : editor.fields.backgroundId ? Number(editor.fields.backgroundId) : null;

  const choose = async (id: number | null) => {
    if (picker?.trackId) await editor.assignTrackBackground(picker.trackId, id);
    else editor.setters.setBackgroundId(id ? String(id) : "");
    setPicker(null);
  };

  return (
    <div
      className={`library-container ${isCourses ? "" : "playlists-mode"}`}
      onDragEnter={isCourses ? upload.onDrag : undefined}
      onDragOver={isCourses ? upload.onDrag : undefined}
      onDragLeave={isCourses ? upload.onDrag : undefined}
      onDrop={isCourses ? upload.onDrop : undefined}
    >
      <PageNav
        tabs={[{ id: "courses", icon: "library_music", label: t("audio.coursesTab") }, { id: "playlists", icon: "playlist_play", label: t("audio.playlistsTab") }]}
        value={mode}
        onChange={(id) => setMode(id as typeof mode)}
        ariaLabel={t("audio.coursesTab")}
        actions={<>{isCourses && (
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <input ref={fileInput} type="file" accept={upload.mode === "zip" ? ARCHIVE_ACCEPT : AUDIO_ACCEPT} multiple={upload.mode === "files"} style={{ display: "none" }}
              onChange={(e) => { upload.select(e.target.files); e.target.value = ""; }} />
            <input
              ref={(el) => {
                folderInput.current = el;
                el?.setAttribute("webkitdirectory", "");
                el?.setAttribute("directory", "");
              }}
              type="file" multiple style={{ display: "none" }}
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                upload.select(files, folderOf(files[0]));
                e.target.value = "";
              }}
            />
            <button type="button" className="btn btn-primary" style={{ height: "40px", padding: "0 16px", fontSize: "0.85rem" }} onClick={upload.toggle}>
              <Icon name="cloud_upload" size={18} />
              <span>Importer</span>
            </button>
          </div>
        )}</>}
      />
      {!isCourses ? <AudioPlaylistManager /> : (
        <>
          <datalist id={PROGRAMS_LIST_ID}>{courses.programs.map((p) => <option key={p} value={p} />)}</datalist>
          {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
          {upload.visible && <UploadPanel upload={upload} onPickFiles={() => fileInput.current?.click()} onPickFolder={() => folderInput.current?.click()} />}
          <CourseGrid courses={courses.courses} loading={courses.loading} onOpen={editor.open} />
          {course && (
            <CourseDrawer editor={editor} course={course} backgrounds={courses.backgrounds} defaultBackground={courses.defaultBackground}
              onPickCourseBackground={() => setPicker({ trackId: null })} onPickTrackBackground={(trackId) => setPicker({ trackId })} />
          )}
          {editor.toDelete && (
            <ConfirmDialog title={t("audio.deleteCourseTitle")} confirmLabel={t("audio.confirmDelete")} cancelLabel={t("common.cancel")} danger onConfirm={editor.remove} onCancel={() => editor.setToDelete(null)}>
              <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
                {t("audio.deleteCourseConfirmBefore")}{" "}
                <strong style={{ color: "var(--text-main)" }}>{editor.toDelete.title}</strong>{" "}
                {t("audio.deleteCourseConfirmAfter", { count: editor.toDelete.track_count })}
              </p>
            </ConfirmDialog>
          )}
          {picker && (
            <BackgroundPicker forTrack={picker.trackId !== null} backgrounds={courses.backgrounds} defaultBackground={courses.defaultBackground}
              selectedId={pickerSelected} onSelect={choose} onClose={() => setPicker(null)} />
          )}
        </>
      )}
    </div>
  );
}
