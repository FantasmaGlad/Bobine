"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { formatMediaDuration } from "@/lib/format";

import { thumbnailUrl } from "./media";
import type { AudioCourseSummary } from "./types";

function groups(courses: AudioCourseSummary[]) {
  const programOf = (c: AudioCourseSummary) => (c.program && c.program.trim() ? c.program : "");
  return Array.from(new Set(courses.map(programOf)))
    .sort((a, b) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b, "fr", { sensitivity: "base" })))
    .map((program) => ({ program, courses: courses.filter((c) => programOf(c) === program) }))
    .filter((g) => g.courses.length > 0);
}

function CourseCard({ course, onOpen }: { course: AudioCourseSummary; onOpen: () => void }) {
  const { t } = useAppSettings();
  const thumb = thumbnailUrl(course.background_thumbnail_path);
  return (
    <div className="video-card program-autre" onClick={onOpen}>
      <div className="thumbnail-wrapper" style={{ background: "var(--bg-surface-elevated)" }}>
        {thumb ? (
          <img src={thumb} alt="" className="card-thumbnail" />
        ) : (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="library_music" size={40} style={{ opacity: 0.25 }} />
          </div>
        )}
        <span className="card-duration">{t("audio.tracksCount", { count: course.track_count })}</span>
      </div>
      <div className="card-content">
        <h4 className="card-title" title={course.title}>{course.title}</h4>
        <div className="card-meta-row">
          <span className="program-badge autre">{course.program || t("audio.noProgram")}</span>
          <span className="release-badge">{formatMediaDuration(course.total_duration_seconds)}</span>
        </div>
      </div>
    </div>
  );
}

export default function CourseGrid({ courses, loading, onOpen }: { courses: AudioCourseSummary[]; loading: boolean; onOpen: (id: number) => void }) {
  const { t } = useAppSettings();
  const centered = { display: "flex", flex: 1, alignItems: "center", justifyContent: "center", minHeight: "300px", color: "var(--text-muted)" } as const;
  if (loading) return <div style={centered}>{t("audio.loadingCourses")}</div>;
  if (courses.length === 0) {
    return (
      <div style={{ ...centered, flexDirection: "column" }}>
        <p style={{ margin: 0, fontWeight: 600 }}>{t("audio.noCoursesTitle")}</p>
        <p style={{ fontSize: "0.85rem", margin: "4px 0 0" }}>{t("audio.noCoursesHint")}</p>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
      {groups(courses).map((group) => (
        <div key={group.program}>
          <h3 style={{ fontSize: "0.85rem", marginBottom: "16px", color: "var(--accent-text)" }}>
            {group.program === "" ? t("audio.noProgram") : group.program}{" "}
            <span style={{ color: "var(--text-dim)" }}>({group.courses.length})</span>
          </h3>
          <div className="videos-grid">
            {group.courses.map((course) => <CourseCard key={course.id} course={course} onOpen={() => onOpen(course.id)} />)}
          </div>
        </div>
      ))}
    </div>
  );
}
