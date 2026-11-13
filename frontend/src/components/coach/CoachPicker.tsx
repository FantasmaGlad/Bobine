"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import SearchBox from "@/components/SearchBox";
import { matchesQuery } from "@/lib/searchText";
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
          {pickerTab === "courses" ? (
            loading ? (
              <p className="live-empty">{t("coach.loadingCourses")}</p>
            ) : filteredCourses.length === 0 ? (
              <p className="live-empty">{t("coach.noCoursesAvailable")}</p>
            ) : (
              filteredCourses.map((c, i) => (
                <button
                  key={c.id}
                  className="coach-course-item olc-press olc-card-hover olc-anim-in"
                  style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
                  onClick={() => launchCourse(c.id)}
                >
                  <span className="coach-course-item-accent" style={{ background: "var(--accent-primary)" }} />
                  <span className="coach-course-item-body">
                    <span className="coach-course-item-title">{c.title}</span>
                    <span className="coach-course-item-meta">
                      {c.program || t("coach.otherProgram")} · {t("coach.tracksCount", { count: c.track_count })}
                    </span>
                  </span>
                  <Icon name="play_circle" size={22} />
                </button>
              ))
            )
          ) : filteredAudioPlaylists.length === 0 ? (
            <p className="live-empty">{t("coach.noPlaylistsAvailable")}</p>
          ) : (
            filteredAudioPlaylists.map((p, i) => (
              <button
                key={p.id}
                className="coach-course-item olc-press olc-card-hover olc-anim-in"
                style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
                onClick={() => launchAudioPlaylist(p.id)}
              >
                <span className="coach-course-item-accent" style={{ background: "var(--accent-primary)" }} />
                <span className="coach-course-item-body">
                  <span className="coach-course-item-title">{p.name}</span>
                  <span className="coach-course-item-meta">
                    {t("coach.tracksInPlaylist", { count: p.item_count })}
                  </span>
                </span>
                <Icon name="play_circle" size={22} />
              </button>
            ))
          )}
        </div>
        {children}
      </div>
  );
}
