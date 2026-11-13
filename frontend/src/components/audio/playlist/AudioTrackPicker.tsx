"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import SearchBox from "@/components/SearchBox";
import { getApiUrl } from "@/lib/apiUrl";
import { formatMediaDuration } from "@/lib/format";
import { matchesQuery } from "@/lib/searchText";
import type { AudioCourseSummary, AudioTrackSummary, Sequencer } from "./types";

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
  const { handleDragStart, resetDragState } = sequencer;
  const [trackSearch, setTrackSearch] = useState<string>("");
  const [trackProgramFilter, setTrackProgramFilter] = useState<string>("");
  const [expandedCourseIds, setExpandedCourseIds] = useState<Set<number>>(new Set());
  const getCourseThumbSrc = (course: AudioCourseSummary) => {
    if (!course.background_thumbnail_path) return null;
    const filename = course.background_thumbnail_path.split("/").pop();
    if (!filename) return null;
    return getApiUrl(`/thumbnails/${filename}`);
  };

  const toggleCourseExpanded = (courseId: number) => {
    setExpandedCourseIds((prev) => {
      const next = new Set(prev);
      if (next.has(courseId)) next.delete(courseId);
      else next.add(courseId);
      return next;
    });
  };

  const availablePrograms = React.useMemo(() => {
    const set = new Set<string>();
    for (const c of courses) if (c.program) set.add(c.program);
    return Array.from(set).sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));
  }, [courses]);

  const filteredTracks = tracks.filter((tr) => {
    const matchesSearch =
      matchesQuery(tr.title, trackSearch) || matchesQuery(tr.course_title, trackSearch);
    const matchesProgram = !trackProgramFilter || tr.course_program === trackProgramFilter;
    return matchesSearch && matchesProgram;
  });

  const groupedCourses = React.useMemo(() => {
    const byId = new Map<number, AudioTrackSummary[]>();
    for (const tr of filteredTracks) {
      const list = byId.get(tr.course_id);
      if (list) list.push(tr);
      else byId.set(tr.course_id, [tr]);
    }
    return courses
      .filter((c) => byId.has(c.id))
      .map((c) => ({ course: c, tracks: byId.get(c.id)! }));
  }, [courses, filteredTracks]);

  const isSearching = trackSearch.trim().length > 0;

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
                    groupedCourses.map(({ course, tracks: courseTracks }) => {
                      const thumbSrc = getCourseThumbSrc(course);
                      const expanded = isSearching || expandedCourseIds.has(course.id);
                      return (
                        <div key={course.id} className="picker-course-card">
                          <div className="picker-course-header" onClick={() => toggleCourseExpanded(course.id)}>
                            <div className="picker-course-thumb">
                              {thumbSrc ? (
                                // eslint-disable-next-line @next/next/no-img-element
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
                                <div
                                  key={track.id}
                                  className="picker-track-row"
                                  draggable={!isMobile}
                                  onDragStart={(e) => handleDragStart(e, track.id, "library")}
                                  onDragEnd={resetDragState}
                                >
                                  {!isMobile && <div className="drag-handle" style={{ padding: 0 }}><Icon name="drag_indicator" size={14} /></div>}
                                  <span style={{ flex: 1, minWidth: 0, fontSize: "0.78rem", fontWeight: 600, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                    {track.number ? `${track.number}. ` : ""}{track.title}
                                  </span>
                                  <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", flexShrink: 0 }}>
                                    {formatMediaDuration(track.duration_seconds)}
                                  </span>
                                  <button
                                    type="button"
                                    className="btn btn-secondary"
                                    style={{ height: "22px", padding: "0 6px", fontSize: "0.68rem", fontWeight: 700, flexShrink: 0 }}
                                    onClick={() => handleAddTrack(track)}
                                  >
                                    {t("audioPlaylists.addShort")}
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
  );
}
