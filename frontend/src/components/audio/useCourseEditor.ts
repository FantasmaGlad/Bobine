"use client";

import React, { useState } from "react";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

import type { AudioCourseDetail, AudioCourseSummary, AudioTrack } from "./types";
import type { AudioCourses } from "./useAudioCourses";

const json = (method: string, body: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function useCourseEditor(courses: AudioCourses, showToast: ShowToast) {
  const { t } = useAppSettings();
  const [course, setCourse] = useState<AudioCourseDetail | null>(null);
  const [title, setTitle] = useState("");
  const [program, setProgram] = useState("");
  const [release, setRelease] = useState("");
  const [backgroundId, setBackgroundId] = useState("");
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState<AudioCourseSummary | null>(null);

  const open = async (courseId: number) => {
    const res = await fetch(getApiUrl(`/audio/${courseId}`), { cache: "no-store" });
    if (!res.ok) return showToast(t("audio.loadCourseError"), "error");
    const detail: AudioCourseDetail = await res.json();
    setCourse(detail);
    setTitle(detail.title);
    setProgram(detail.program || "");
    setRelease(detail.release || "");
    setBackgroundId(detail.background_id ? String(detail.background_id) : "");
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!course) return;
    setSaving(true);
    try {
      const res = await fetch(getApiUrl(`/audio/${course.id}`), json("PUT", {
        title, program: program || null, release: release || null,
        background_id: backgroundId ? Number(backgroundId) : null, clear_background: !backgroundId,
      }));
      if (!res.ok) return showToast(t("audio.saveError"), "error");
      setCourse(await res.json());
      showToast(t("audio.updatedToast"));
      courses.refresh();
    } finally {
      setSaving(false);
    }
  };

  const reorder = (from: number, to: number) => {
    if (!course || from === to) return;
    const tracks = [...course.tracks];
    const [moved] = tracks.splice(from, 1);
    tracks.splice(to, 0, moved);
    setCourse({ ...course, tracks });
    fetch(getApiUrl(`/audio/${course.id}/tracks/reorder`), json("PUT", { track_ids: tracks.map((tr) => tr.id) }));
  };

  const assignTrackBackground = async (trackId: number, bgId: number | null) => {
    if (!course) return;
    try {
      const res = await fetch(getApiUrl(`/audio/${course.id}/tracks/${trackId}`), json("PUT", { background_id: bgId, clear_background: bgId === null }));
      if (!res.ok) return showToast(t("audio.saveError"), "error");
      const updated: AudioTrack = await res.json();
      setCourse({ ...course, tracks: course.tracks.map((tr) => (tr.id === trackId ? updated : tr)) });
      showToast(t("audio.updatedToast"));
    } catch {
      showToast(t("audio.connectionError"), "error");
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    try {
      const res = await fetch(getApiUrl(`/audio/${toDelete.id}`), { method: "DELETE" });
      if (!res.ok) return showToast(t("audio.deleteError"), "error");
      showToast(t("audio.deletedToast"));
      courses.setCourses((prev) => prev.filter((c) => c.id !== toDelete.id));
      if (course?.id === toDelete.id) setCourse(null);
    } finally {
      setToDelete(null);
    }
  };

  return {
    course, close: () => setCourse(null), open, save, saving, reorder, assignTrackBackground, toDelete, setToDelete, remove,
    fields: { title, program, release, backgroundId }, setters: { setTitle, setProgram, setRelease, setBackgroundId },
  };
}

export type CourseEditor = ReturnType<typeof useCourseEditor>;
