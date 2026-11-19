"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import SearchBox from "@/components/SearchBox";
import { matchesQuery } from "@/lib/searchText";
import PickerItem from "./PickerItem";
import type { AudioCourseSummary, AudioPlaylistSummary } from "./types";

interface CoachPickerProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  connected: boolean;
  loading: boolean;
  courses: AudioCourseSummary[];
  audioPlaylists: AudioPlaylistSummary[];
  handleBackFromPicker: () => void;
  openNav: () => void;
  launchCourse: (id: number) => void;
  launchAudioPlaylist: (id: number) => void;
  children?: React.ReactNode;
}
type Translate = CoachPickerProps["t"];

function PickerList({ t, tab, loading, courses, audioPlaylists, launchCourse, launchAudioPlaylist }: {
  t: Translate; tab: "courses" | "playlists"; loading: boolean; courses: AudioCourseSummary[]; audioPlaylists: AudioPlaylistSummary[];
  launchCourse: (id: number) => void; launchAudioPlaylist: (id: number) => void;
}) {
  if (tab === "courses") {
    if (loading) return <p className="live-empty">{t("coach.loadingCourses")}</p>;
    if (courses.length === 0) return <p className="live-empty">{t("coach.noCoursesAvailable")}</p>;
    return (
      <>
        {courses.map((c, i) => (
          <PickerItem key={c.id} index={i} title={c.title} onLaunch={() => launchCourse(c.id)}
            meta={<>{c.program || t("coach.otherProgram")} · {t("coach.tracksCount", { count: c.track_count })}</>} />
        ))}
      </>
    );
  }
  if (audioPlaylists.length === 0) return <p className="live-empty">{t("coach.noPlaylistsAvailable")}</p>;
  return (
    <>
      {audioPlaylists.map((p, i) => (
        <PickerItem key={p.id} index={i} title={p.name} onLaunch={() => launchAudioPlaylist(p.id)}
          meta={t("coach.tracksInPlaylist", { count: p.item_count })} />
      ))}
    </>
  );
}

export default function CoachPicker({
  t, connected, loading, courses, audioPlaylists, handleBackFromPicker, openNav, launchCourse, launchAudioPlaylist, children,
}: CoachPickerProps) {
  const [pickerTab, setPickerTab] = useState<"courses" | "playlists">("courses");
  const [search, setSearch] = useState("");
  const searchSuggestions = [...courses.map((c) => c.title), ...audioPlaylists.map((p) => p.name)];
  const filteredCourses = courses.filter((c) => matchesQuery(c.title, search));
  const filteredAudioPlaylists = audioPlaylists.filter((p) => matchesQuery(p.name, search));
  return (
      <div className="coach-screen coach-picker-screen">
        <div className="coach-picker-topbar">
          <button
            type="button"
            className="coach-icon-btn olc-press"
            onClick={handleBackFromPicker}
            title={t("coach.backToDashboard")}
          >
            <Icon name="arrow_back" size={20} />
          </button>
          <button className="coach-icon-btn olc-press" onClick={openNav} title={t("coach.otherFunctions")}>
            <Icon name="menu" size={20} />
          </button>
        </div>
        <div className="coach-picker-header">
          <h1 className="coach-picker-title">{t("coach.title")}</h1>
          <p className="coach-picker-subtitle">
            {connected ? t("coach.chooseCourseHint") : t("coach.connectingHint")}
          </p>
          <SearchBox
            className="search-input coach-picker-search"
            placeholder={t("coach.searchPlaceholder")}
            value={search}
            onChange={setSearch}
            suggestions={searchSuggestions}
          />
          <div className="coach-picker-tabs">
            <button
              type="button"
              className={`speed-btn ${pickerTab === "courses" ? "active" : ""}`}
              onClick={() => setPickerTab("courses")}
            >
              {t("coach.coursesTab")}
            </button>
            <button
              type="button"
              className={`speed-btn ${pickerTab === "playlists" ? "active" : ""}`}
              onClick={() => setPickerTab("playlists")}
            >
              {t("coach.playlistsTab")}
            </button>
          </div>
        </div>
        <div className="coach-picker-list">
          <PickerList t={t} tab={pickerTab} loading={loading} courses={filteredCourses} audioPlaylists={filteredAudioPlaylists}
            launchCourse={launchCourse} launchAudioPlaylist={launchAudioPlaylist} />
        </div>
        {children}
      </div>
  );
}
