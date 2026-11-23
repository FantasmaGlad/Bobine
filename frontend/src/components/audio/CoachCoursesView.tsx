"use client";

import { useState } from "react";

import BackgroundPicker from "@/components/audio/BackgroundPicker";
import CourseDrawer from "@/components/audio/CourseDrawer";
import CourseGrid from "@/components/audio/CourseGrid";
import { PROGRAMS_LIST_ID } from "@/components/audio/types";
import UploadPanel from "@/components/audio/UploadPanel";
import type { AudioCourses } from "@/components/audio/useAudioCourses";
import type { AudioUpload } from "@/components/audio/useAudioUpload";
import { useCourseEditor } from "@/components/audio/useCourseEditor";
import ConfirmDialog from "@/components/ConfirmDialog";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { ShowToast, ToastState } from "@/lib/useToast";

type Picker = { trackId: number | null } | null;

interface Props {
  courses: AudioCourses;
  upload: AudioUpload;
  toast: ToastState | null;
  showToast: ShowToast;
  onPickFiles: () => void;
  onPickFolder: () => void;
}

export default function CoachCoursesView({ courses, upload, toast, showToast, onPickFiles, onPickFolder }: Props) {
  const { t } = useAppSettings();
  const [picker, setPicker] = useState<Picker>(null);
  const editor = useCourseEditor(courses, showToast);
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
    <>
      <datalist id={PROGRAMS_LIST_ID}>{courses.programs.map((p) => <option key={p} value={p} />)}</datalist>
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
      {upload.visible && <UploadPanel upload={upload} onPickFiles={onPickFiles} onPickFolder={onPickFolder} />}
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
  );
}
