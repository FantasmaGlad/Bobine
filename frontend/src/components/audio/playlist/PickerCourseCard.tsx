"use client";

import React from "react";
import Icon from "@/components/Icon";
import { thumbnailUrl } from "@/lib/thumbnail";
import PickerTrackRow from "./PickerTrackRow";
import type { AudioCourseSummary, AudioTrackSummary, Sequencer } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export default function PickerCourseCard({ t, isMobile, course, courseTracks, expanded, onToggle, sequencer, handleAddTrack, handleAddWholeCourse }: {
  t: Translate; isMobile: boolean; course: AudioCourseSummary; courseTracks: AudioTrackSummary[]; expanded: boolean; onToggle: () => void;
  sequencer: Sequencer; handleAddTrack: (track: AudioTrackSummary) => void; handleAddWholeCourse: (courseId: number) => void;
}) {
  const thumbSrc = thumbnailUrl(course.background_thumbnail_path);
  return (
    <div className="picker-course-card">
    <div className="picker-course-header" onClick={onToggle}>
      <div className="picker-course-thumb">
        {thumbSrc ? (
          <img src={thumbSrc} alt="" />
        ) : (
          <Icon name="library_music" size={18} style={{ opacity: 0.3 }} />
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {course.title}
        </div>
        <div style={{ display: "flex", gap: "6px", alignItems: "center", marginTop: "1px" }}>
          {course.program && (
            <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
              {course.program}
            </span>
          )}
          <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
            {t("audioPlaylists.tracksInCourse", { count: courseTracks.length })}
          </span>
        </div>
      </div>
      <button
        type="button"
        className="btn btn-secondary"
        style={{ height: "26px", padding: "0 8px", fontSize: "0.7rem", fontWeight: 700, flexShrink: 0 }}
        onClick={(e) => {
          e.stopPropagation();
          handleAddWholeCourse(course.id);
        }}
        title={t("audioPlaylists.addWholeCourse")}
      >
        <Icon name="playlist_add" size={14} />
        {t("audioPlaylists.addWholeCourse")}
      </button>
      <Icon name={expanded ? "expand_less" : "expand_more"} size={18} color="var(--text-muted)" />
    </div>

      {expanded && (
        <div className="picker-course-tracks">
          {courseTracks.map((track) => (
            <PickerTrackRow key={track.id} t={t} isMobile={isMobile} track={track} sequencer={sequencer} onAdd={() => handleAddTrack(track)} />
          ))}
        </div>
      )}
    </div>
  );
}
