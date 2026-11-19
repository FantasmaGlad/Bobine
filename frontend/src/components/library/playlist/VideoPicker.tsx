"use client";
import React, { useState } from "react";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import SearchBox from "@/components/SearchBox";
import { matchesQuery } from "@/lib/searchText";
import PickerVideoCard from "./PickerVideoCard";
import type { Sequencer, Video } from "./types";

interface VideoPickerProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  isMobile: boolean;
  videos: Video[];
  sequencer: Sequencer;
  handleAddVideo: (video: Video) => void;
}

export default function VideoPicker({ t, isMobile, videos, sequencer, handleAddVideo }: VideoPickerProps) {
  const [videoSearch, setVideoSearch] = useState<string>("");
  const [videoProgramFilter, setVideoProgramFilter] = useState<string>("");

  const availablePrograms = React.useMemo(() => {
    const set = new Set<string>();
    for (const v of videos) if (v.program) set.add(v.program);
    return Array.from(set).sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));
  }, [videos]);

  const filteredVideos = videos.filter((v) => {
    const matchesSearch =
      matchesQuery(`${v.title} ${v.program ?? ""}`, videoSearch) ||
      (v.release && v.release.includes(videoSearch));
    const matchesProgram = !videoProgramFilter || v.program === videoProgramFilter;
    return matchesSearch && matchesProgram;
  });

  return (
              <div className="library-picker" style={isMobile ? { height: "auto", maxHeight: "360px" } : undefined}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="form-label" style={{ fontSize: "0.75rem", margin: 0, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}>
                    {t("playlists.libraryPickerLabel")}
                  </span>
                </div>

                <div style={{ display: "flex", gap: "8px", flexWrap: isMobile ? "wrap" : "nowrap" }}>
                  <div style={{ flex: 1, minWidth: isMobile ? "100%" : undefined }}>
                    <SearchBox
                      className="form-control"
                      style={{ height: "32px", fontSize: "0.8rem", padding: "0 10px" }}
                      placeholder={t("playlists.videoSearchPlaceholder")}
                      value={videoSearch}
                      onChange={setVideoSearch}
                      suggestions={videos.flatMap((v) => (v.program ? [v.title, v.program] : [v.title]))}
                    />
                  </div>
                  <ResponsiveSelect
                    style={{ minHeight: "32px", fontSize: "0.8rem", padding: "0 8px" }}
                    value={videoProgramFilter}
                    onChange={setVideoProgramFilter}
                    placeholder={t("playlists.allProgramsShort")}
                    title={t("playlists.allProgramsShort")}
                    options={availablePrograms.map((p) => ({ value: p, label: p }))}
                  />
                </div>

                <div className="library-picker-list">
                  {filteredVideos.length === 0 ? (
                    <div style={{ gridColumn: "1 / -1", textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem", padding: "16px" }}>
                      {t("playlists.noMatchingVideos")}
                    </div>
                  ) : (
                    filteredVideos.map((video) => (
                      <PickerVideoCard key={video.id} t={t} isMobile={isMobile} video={video} sequencer={sequencer} onAdd={() => handleAddVideo(video)} />
                    ))
                  )}
                </div>
              </div>
  );
}
