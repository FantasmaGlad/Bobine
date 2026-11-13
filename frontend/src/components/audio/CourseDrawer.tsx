"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

import CourseBackground from "./CourseBackground";
import CourseTracks from "./CourseTracks";
import { PROGRAMS_LIST_ID, type AudioCourseDetail, type BackgroundOption } from "./types";
import type { CourseEditor } from "./useCourseEditor";

interface Props {
  editor: CourseEditor;
  course: AudioCourseDetail;
  backgrounds: BackgroundOption[];
  defaultBackground: BackgroundOption | null;
  onPickCourseBackground: () => void;
  onPickTrackBackground: (trackId: number) => void;
}

const SECTION = { fontSize: "0.85rem", fontWeight: 800, borderBottom: "1px solid var(--border-color)", paddingBottom: "6px" } as const;

function Metadata({ editor }: { editor: CourseEditor }) {
  const { t } = useAppSettings();
  const { fields, setters } = editor;
  return (
    <>
      <div className="form-group">
        <label className="form-label">{t("audio.titleLabel")}</label>
        <input type="text" className="form-control" value={fields.title} onChange={(e) => setters.setTitle(e.target.value)} required />
      </div>
      <div style={{ display: "flex", gap: "12px" }}>
        <div className="form-group" style={{ flex: 1, minWidth: 0 }}>
          <label className="form-label">{t("audio.programLabel")}</label>
          <input type="text" list={PROGRAMS_LIST_ID} className="form-control" placeholder={t("audio.programPlaceholder")} value={fields.program} onChange={(e) => setters.setProgram(e.target.value)} />
        </div>
        <div className="form-group" style={{ flex: 1, minWidth: 0 }}>
          <label className="form-label">{t("audio.releaseLabel")}</label>
          <input type="text" className="form-control" value={fields.release} onChange={(e) => setters.setRelease(e.target.value)} />
        </div>
      </div>
    </>
  );
}

export default function CourseDrawer({ editor, course, backgrounds, defaultBackground, onPickCourseBackground, onPickTrackBackground }: Props) {
  const { t } = useAppSettings();
  const chosen = editor.fields.backgroundId;
  return (
    <>
      <div className="detail-drawer-overlay" onClick={editor.close} />
      <div className="detail-drawer">
        <div className="drawer-header">
          <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", maxWidth: "80%" }}>{course.title}</h3>
          <button aria-label={t("common.close")} className="close-btn" onClick={editor.close}><Icon name="close" size={20} /></button>
        </div>
        <div className="drawer-body">
          <form className="drawer-form" onSubmit={editor.save}>
            <h4 style={{ ...SECTION, margin: "0 0 8px" }}>{t("audio.metadataSectionTitle")}</h4>
            <Metadata editor={editor} />
            <CourseBackground selected={backgrounds.find((b) => String(b.id) === chosen)} fallback={defaultBackground} chosenId={chosen} onChange={onPickCourseBackground} />
            <h4 style={{ ...SECTION, margin: "16px 0 8px" }}>{t("audio.tracksSectionTitle", { count: course.tracks.length })}</h4>
            <CourseTracks tracks={course.tracks} backgrounds={backgrounds} onReorder={editor.reorder} onPickBackground={onPickTrackBackground} />
            <div className="drawer-actions">
              <button type="submit" className="btn btn-primary" style={{ flex: 1, height: "48px" }} disabled={editor.saving}>
                {editor.saving ? t("common.saving") : t("common.save")}
              </button>
              <button type="button" className="btn btn-danger" style={{ height: "48px" }} onClick={() => editor.setToDelete(course)}>{t("common.delete")}</button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}
