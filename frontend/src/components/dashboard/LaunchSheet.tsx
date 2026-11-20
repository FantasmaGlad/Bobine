"use client";
import React, { useState } from "react";
import Sheet from "@/components/Sheet";
import { matchesQuery } from "@/lib/searchText";
import LaunchHeader from "./launch/LaunchHeader";
import LaunchLists, { type LaunchTab } from "./launch/LaunchLists";
import { LaunchPreview, PreviewFooter } from "./launch/LaunchPreview";

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
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
}

export default function LaunchSheet({ t, open, onClose, videos, playlists, backgrounds, sendCommand }: LaunchSheetProps) {
  const [launchSearch, setLaunchSearch] = useState("");
  const [launchTab, setLaunchTab] = useState<LaunchTab>("videos");
  const [previewVideoId, setPreviewVideoId] = useState<number | null>(null);
  const closeLaunchSheet = () => {
    onClose();
    setPreviewVideoId(null);
    setLaunchSearch("");
  };
  const launch = (command: string, params: Record<string, unknown>) => {
    sendCommand(command, params);
    closeLaunchSheet();
  };
  const previewVideo = previewVideoId !== null ? videos.find((v) => v.id === previewVideoId) ?? null : null;
  const launchSuggestions = [
    ...videos.flatMap((v) => (v.program ? [v.title, v.program] : [v.title])),
    ...playlists.map((p) => p.name),
    ...backgrounds.map((b) => b.title),
  ];
  const filteredVideos = videos.filter((v) => matchesQuery(`${v.title} ${v.program ?? ""}`, launchSearch));
  const filteredPlaylists = playlists.filter((p) => matchesQuery(p.name, launchSearch));
  const filteredBackgrounds = backgrounds.filter((b) => matchesQuery(b.title, launchSearch));
  const counts = { videos: filteredVideos.length, playlists: filteredPlaylists.length, backgrounds: filteredBackgrounds.length };

  return (
    <Sheet
      open={open}
      onClose={closeLaunchSheet}
      tall
      closeLabel={t("mobileRemote.close")}
      title={previewVideo ? t("mobileRemote.preview") : t("mobileRemote.launchTitle")}
      header={previewVideo ? undefined : (
        <LaunchHeader search={launchSearch} onSearch={setLaunchSearch} suggestions={launchSuggestions} tab={launchTab} onTab={setLaunchTab} counts={counts} t={t} />
      )}
      footer={previewVideo ? (
        <PreviewFooter onBack={() => setPreviewVideoId(null)} onLaunch={() => launch("load", { video_id: previewVideo.id })} t={t} />
      ) : undefined}
    >
      {previewVideo ? (
        <LaunchPreview video={previewVideo} t={t} />
      ) : (
        <LaunchLists tab={launchTab} videos={filteredVideos} playlists={filteredPlaylists} backgrounds={filteredBackgrounds} onPreview={setPreviewVideoId} onLaunch={launch} t={t} />
      )}
    </Sheet>
  );
}
