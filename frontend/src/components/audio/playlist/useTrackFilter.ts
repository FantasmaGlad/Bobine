"use client";

import React, { useState } from "react";
import { matchesQuery } from "@/lib/searchText";
import type { AudioCourseSummary, AudioTrackSummary } from "./types";

export function useTrackFilter(tracks: AudioTrackSummary[], courses: AudioCourseSummary[]) {
  const [trackSearch, setTrackSearch] = useState<string>("");
  const [trackProgramFilter, setTrackProgramFilter] = useState<string>("");
  const [expandedCourseIds, setExpandedCourseIds] = useState<Set<number>>(new Set());

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

  return { trackSearch, setTrackSearch, trackProgramFilter, setTrackProgramFilter, expandedCourseIds, toggleCourseExpanded, availablePrograms, groupedCourses, isSearching };
}
