"use client";

import React, { useCallback, useEffect, useState } from "react";
import PlaylistEditorLayout from "@/components/playlist-editor/PlaylistEditorLayout";
import { usePlaylistEditor } from "@/components/playlist-editor/usePlaylistEditor";
import { usePlaylistLaunch } from "@/components/playlist-editor/usePlaylistLaunch";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { useIsMobile } from "@/lib/useIsMobile";
import { usePlaylistSequencer } from "@/lib/usePlaylistSequencer";
import { useToast } from "@/lib/useToast";
import AudioSequencer from "./playlist/AudioSequencer";
import AudioTrackPicker from "./playlist/AudioTrackPicker";
import type { AudioCourseSummary, AudioPlaylistDetail, AudioPlaylistItemInput, AudioTrackSummary, BackgroundSummary, PlaylistDraftItem } from "./playlist/types";

const itemsFrom = (detail: AudioPlaylistDetail): PlaylistDraftItem[] =>
  detail.items.map((item) => ({ track: item.track, backgroundId: item.background?.id ?? null }));
const payload = (items: PlaylistDraftItem[]): AudioPlaylistItemInput[] =>
  items.map((item, index) => ({ audio_track_id: item.track.id, position: index, background_id: item.backgroundId }));

function quiet<T>(path: string, apply: (data: T) => void) {
  return fetch(getApiUrl(path), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) apply(await res.json());
    })
    .catch(() => {});
}

export default function AudioPlaylistManager() {
  const { t } = useAppSettings();
  const isMobile = useIsMobile();
  const { toast, showToast } = useToast();
  const [tracks, setTracks] = useState<AudioTrackSummary[]>([]);
  const [courses, setCourses] = useState<AudioCourseSummary[]>([]);
  const [backgrounds, setBackgrounds] = useState<BackgroundSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const editor = usePlaylistEditor<PlaylistDraftItem, AudioPlaylistDetail>({ endpoint: "/audio-playlists", prefix: "audioPlaylists", itemsFrom, payload, t, showToast });
  const { draft, fetchPlaylists } = editor;
  const sequencer = usePlaylistSequencer<PlaylistDraftItem>(draft.setPlaylistItems, (id) => {
    const track = tracks.find((tr) => tr.id === id);
    return track ? { track, backgroundId: null } : undefined;
  });
  const launch = usePlaylistLaunch("audioPlaylists", t, showToast, "load_audio_playlist", "audio_playlist_id");

  const fetchTracks = useCallback(() => fetch(getApiUrl("/audio/tracks"), { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) setTracks(await res.json());
    })
    .catch(() => showToast(t("audioPlaylists.coursesNetworkError"), "error")), [showToast, t]);

  useEffect(() => {
    Promise.all([fetchPlaylists(), fetchTracks(), quiet("/audio", setCourses), quiet("/backgrounds", setBackgrounds)])
      .finally(() => setLoading(false));
  }, [fetchPlaylists, fetchTracks]);

  const handleAddTrack = (track: AudioTrackSummary) => {
    draft.setPlaylistItems((prev) => [...prev, { track, backgroundId: null }]);
    showToast(t("audioPlaylists.addedToast", { title: track.title }));
  };

  const handleAddWholeCourse = (courseId: number) => {
    const courseTracks = tracks.filter((tr) => tr.course_id === courseId);
    if (courseTracks.length === 0) return;
    draft.setPlaylistItems((prev) => [...prev, ...courseTracks.map((track) => ({ track, backgroundId: null }))]);
    const course = courses.find((c) => c.id === courseId);
    showToast(t("audioPlaylists.addedWholeCourseToast", { title: course?.title ?? "", count: courseTracks.length }));
  };

  const handleSetTrackBackground = (index: number, backgroundId: number | null) => {
    draft.setPlaylistItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], backgroundId };
      return copy;
    });
  };

  return (
    <PlaylistEditorLayout
      editor={editor} prefix="audioPlaylists" placeholderIcon="queue_music" t={t} isMobile={isMobile} loading={loading} toast={toast}
      totalDurationSeconds={draft.playlistItems.reduce((acc, item) => acc + (item.track.duration_seconds ?? 0), 0)}
      statusOnMobile={false} onLaunch={launch}
      sequencer={<AudioSequencer t={t} isMobile={isMobile} playlistItems={draft.playlistItems} backgrounds={backgrounds} sequencer={sequencer} handleSetTrackBackground={handleSetTrackBackground} />}
      picker={<AudioTrackPicker key={draft.selectedPlaylistId ?? "new"} t={t} isMobile={isMobile} tracks={tracks} courses={courses} sequencer={sequencer} handleAddTrack={handleAddTrack} handleAddWholeCourse={handleAddWholeCourse} />}
    />
  );
}
