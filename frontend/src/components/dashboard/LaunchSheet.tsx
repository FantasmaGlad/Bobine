"use client";
import React, { useState } from "react";
import CourseCard from "@/components/CourseCard";
import Icon from "@/components/Icon";
import SearchBox from "@/components/SearchBox";
import Sheet from "@/components/Sheet";
import { courseThumbSrc, formatClock } from "@/lib/courseMeta";
import { formatCleanDescription } from "@/lib/formatDescription";
import { matchesQuery } from "@/lib/searchText";
import { getAudioQualityBadge, getResolutionBadge } from "@/lib/videoBadges";

export interface VideoSummary {
  id: number;
  title: string;
  program: string | null;
  release?: string | null;
  duration_seconds: number | null;
  thumbnail_path?: string | null;
  description?: string | null;
  width?: number | null;
  height?: number | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
}

export interface PlaylistSummary {
  id: number;
  name: string;
  item_count: number;
}

export interface BackgroundSummary {
  id: number;
  title: string;
  thumbnail_path?: string | null;
}

interface LaunchSheetProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  open: boolean;
  onClose: () => void;
  videos: VideoSummary[];
  playlists: PlaylistSummary[];
  backgrounds: BackgroundSummary[];
  getApiUrl: (path: string) => string;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
}

export default function LaunchSheet({ t, open, onClose, videos, playlists, backgrounds, getApiUrl, sendCommand }: LaunchSheetProps) {
  const [launchSearch, setLaunchSearch] = useState("");
  const [launchTab, setLaunchTab] = useState<"videos" | "playlists" | "backgrounds">("videos");
  const [previewVideoId, setPreviewVideoId] = useState<number | null>(null);
  const closeLaunchSheet = () => {
    onClose();
    setPreviewVideoId(null);
    setLaunchSearch("");
  };
  const previewVideo = previewVideoId !== null ? videos.find((v) => v.id === previewVideoId) ?? null : null;
  const releaseLabel = (release: string) => t("mobileRemote.releaseShort", { release });
  const launchSuggestions = [
    ...videos.flatMap((v) => (v.program ? [v.title, v.program] : [v.title])),
    ...playlists.map((p) => p.name),
    ...backgrounds.map((b) => b.title),
  ];
  const filteredVideos = videos.filter((v) => matchesQuery(`${v.title} ${v.program ?? ""}`, launchSearch));
  const filteredPlaylists = playlists.filter((p) => matchesQuery(p.name, launchSearch));
  const filteredBackgrounds = backgrounds.filter((b) => matchesQuery(b.title, launchSearch));

  return (
    <Sheet
      open={open}
      onClose={closeLaunchSheet}
      tall
      closeLabel={t("mobileRemote.close")}
      title={previewVideo ? t("mobileRemote.preview") : t("mobileRemote.launchTitle")}
      header={
        previewVideo ? undefined : (
          <>
            <SearchBox
              className="search-input sheet-search"
              placeholder={t("mobileRemote.searchPlaceholder")}
              value={launchSearch}
              onChange={setLaunchSearch}
              suggestions={launchSuggestions}
            />
            <div className="view-toggle launch-tabs" style={{ marginTop: 10 }}>
              {(
                [
                  ["videos", t("mobileRemote.tabCourses"), filteredVideos.length],
                  ["playlists", t("mobileRemote.tabPlaylists"), filteredPlaylists.length],
                  ["backgrounds", t("mobileRemote.tabBackgrounds"), filteredBackgrounds.length],
                ] as const
              ).map(([key, label, count]) => (
                <button key={key} type="button" className={`view-btn olc-press ${launchTab === key ? "active" : ""}`} onClick={() => setLaunchTab(key)}>
                  {label} <span style={{ opacity: 0.6 }}>{count}</span>
                </button>
              ))}
            </div>
          </>
        )
      }
      footer={
        previewVideo ? (
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setPreviewVideoId(null)}>
              {t("mobileRemote.back")}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                sendCommand("load", { video_id: previewVideo.id });
                closeLaunchSheet();
              }}
            >
              <Icon name="play_arrow" size={20} filled />
              {t("mobileRemote.launchNow")}
            </button>
          </>
        ) : undefined
      }
    >
      {previewVideo ? (
        <div className="launch-preview">
          <CourseCard
            variant="hero"
            getApiUrl={getApiUrl}
            releaseLabel={releaseLabel}
            fallbackProgram={t("mobileRemote.otherProgram")}
            course={previewVideo}
          />
          <div className="launch-preview__specs">
            {getResolutionBadge(previewVideo.width, previewVideo.height) && <span>{getResolutionBadge(previewVideo.width, previewVideo.height)}</span>}
            {getAudioQualityBadge(previewVideo.audio_channels, previewVideo.audio_codec, null, t) && (
              <span>{getAudioQualityBadge(previewVideo.audio_channels, previewVideo.audio_codec, null, t)}</span>
            )}
            {previewVideo.duration_seconds ? <span>{formatClock(previewVideo.duration_seconds)}</span> : null}
          </div>
          {previewVideo.description ? <p className="launch-preview__description">{formatCleanDescription(previewVideo.description)}</p> : null}
        </div>
      ) : (
        <>
          {launchTab === "videos" &&
            filteredVideos.map((v) => (
              <CourseCard
                key={`v-${v.id}`}
                getApiUrl={getApiUrl}
                releaseLabel={releaseLabel}
                fallbackProgram={t("mobileRemote.otherProgram")}
                course={v}
                onClick={() => setPreviewVideoId(v.id)}
                trailing={<Icon name="chevron_right" size={20} style={{ alignSelf: "center", color: "var(--text-muted)" }} />}
              />
            ))}
          {launchTab === "playlists" &&
            filteredPlaylists.map((p) => (
              <button
                key={`pl-${p.id}`}
                type="button"
                className="sheet-option olc-press"
                onClick={() => {
                  sendCommand("load_playlist", { playlist_id: p.id });
                  closeLaunchSheet();
                }}
              >
                <Icon name="playlist_play" size={22} />
                <span className="sheet-option__text">
                  <span className="sheet-option__label">{p.name}</span>
                  <span className="sheet-option__sub">{t("mobileRemote.coursesCount", { count: p.item_count })}</span>
                </span>
              </button>
            ))}
          {launchTab === "backgrounds" &&
            filteredBackgrounds.map((b) => {
              const thumb = courseThumbSrc(getApiUrl, { thumbnail_path: b.thumbnail_path });
              return (
                <button
                  key={`bg-${b.id}`}
                  type="button"
                  className="sheet-option olc-press"
                  onClick={() => {
                    sendCommand("load_background", { background_id: b.id });
                    closeLaunchSheet();
                  }}
                >
                  {thumb ? <img className="sheet-option__thumb" src={thumb} alt="" loading="lazy" /> : <Icon name="gradient" size={22} />}
                  <span className="sheet-option__text">
                    <span className="sheet-option__label">{b.title}</span>
                    <span className="sheet-option__sub">{t("mobileRemote.backgroundLabel")}</span>
                  </span>
                </button>
              );
            })}
          {((launchTab === "videos" && filteredVideos.length === 0) ||
            (launchTab === "playlists" && filteredPlaylists.length === 0) ||
            (launchTab === "backgrounds" && filteredBackgrounds.length === 0)) && <p className="live-empty">{t("mobileRemote.noResults")}</p>}
        </>
      )}
    </Sheet>
  );
}
