"use client";
import React from "react";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import SearchBox from "@/components/SearchBox";
import PickerCourseCard from "./PickerCourseCard";
import type { AudioCourseSummary, AudioTrackSummary, Sequencer } from "./types";
import { useTrackFilter } from "./useTrackFilter";

interface AudioTrackPickerProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  isMobile: boolean;
  tracks: AudioTrackSummary[];
  courses: AudioCourseSummary[];
  sequencer: Sequencer;
  handleAddTrack: (track: AudioTrackSummary) => void;
  handleAddWholeCourse: (courseId: number) => void;
}

export default function AudioTrackPicker({ t, isMobile, tracks, courses, sequencer, handleAddTrack, handleAddWholeCourse }: AudioTrackPickerProps) {
  const { trackSearch, setTrackSearch, trackProgramFilter, setTrackProgramFilter, expandedCourseIds, toggleCourseExpanded, availablePrograms, groupedCourses, isSearching } = useTrackFilter(tracks, courses);

  return (
              <div className="library-picker" style={{ height: isMobile ? "auto" : "340px", maxHeight: isMobile ? "380px" : undefined }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="form-label" style={{ fontSize: "0.75rem", margin: 0, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}>
                    {t("audioPlaylists.libraryPickerLabel")}
                  </span>
                </div>

                <div style={{ display: "flex", gap: "8px", flexWrap: isMobile ? "wrap" : "nowrap" }}>
                  <div style={{ flex: 1, minWidth: isMobile ? "100%" : undefined }}>
                    <SearchBox
                      className="form-control"
                      style={{ height: "32px", fontSize: "0.8rem", padding: "0 10px" }}
                      placeholder={t("audioPlaylists.courseSearchPlaceholder")}
                      value={trackSearch}
                      onChange={setTrackSearch}
                      suggestions={tracks.flatMap((tr) => [tr.title, tr.course_title])}
                    />
                  </div>
                  <ResponsiveSelect
                    style={{ minHeight: "32px", fontSize: "0.8rem", padding: "0 8px" }}
                    value={trackProgramFilter}
                    onChange={setTrackProgramFilter}
                    placeholder={t("audioPlaylists.allProgramsShort")}
                    title={t("audioPlaylists.allProgramsShort")}
                    options={availablePrograms.map((p) => ({ value: p, label: p }))}
                  />
                </div>

                <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px", paddingRight: "2px" }}>
                  {groupedCourses.length === 0 ? (
                    <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem", padding: "16px" }}>
                      {t("audioPlaylists.noMatchingCourses")}
                    </div>
                  ) : (
                    groupedCourses.map(({ course, tracks: courseTracks }) => (
                      <PickerCourseCard key={course.id} t={t} isMobile={isMobile} course={course} courseTracks={courseTracks}
                        expanded={isSearching || expandedCourseIds.has(course.id)} onToggle={() => toggleCourseExpanded(course.id)}
                        sequencer={sequencer} handleAddTrack={handleAddTrack} handleAddWholeCourse={handleAddWholeCourse} />
                    ))
                  )}
                </div>
              </div>
  );
}
