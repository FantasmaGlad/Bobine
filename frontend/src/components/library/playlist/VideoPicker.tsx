"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import SearchBox from "@/components/SearchBox";
import { getApiUrl } from "@/lib/apiUrl";
import { matchesQuery } from "@/lib/searchText";
import { formatItemDuration, type Sequencer, type Video } from "./types";

interface VideoPickerProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  isMobile: boolean;
  videos: Video[];
  sequencer: Sequencer;
  handleAddVideo: (video: Video) => void;
}

export default function VideoPicker({ t, isMobile, videos, sequencer, handleAddVideo }: VideoPickerProps) {
  const { handleDragStart, resetDragState } = sequencer;
  const [videoSearch, setVideoSearch] = useState<string>("");
  const [videoProgramFilter, setVideoProgramFilter] = useState<string>("");
  const getThumbnailSrc = (video: Video) => {
    if (!video.thumbnail_path) return null;
    const filename = video.thumbnail_path.split("/").pop();
    if (!filename) return null;
    return getApiUrl(`/thumbnails/${filename}`);
  };

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
                    filteredVideos.map((video) => {
                      const thumbSrc = getThumbnailSrc(video);
                      return (
                        <div
                          key={video.id}
                          className={`picker-card ${isMobile ? "always-show-add" : ""}`}
                          draggable={!isMobile}
                          onDragStart={(e) => handleDragStart(e, video.id, "library")}
                          onDragEnd={resetDragState}
                          title={video.title}
                        >
                          <div className="thumbnail-wrapper">
                            {thumbSrc ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={thumbSrc} alt="" className="card-thumbnail" />
                            ) : (
                              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                <Icon name="movie" size={20} style={{ opacity: 0.25 }} />
                              </div>
                            )}
                            <span className="card-duration" style={{ fontSize: "0.65rem", padding: "1px 4px" }}>
                              {formatItemDuration(video.duration_seconds)}
                            </span>
                          </div>
                          <div className="picker-card-content">
                            <span className="picker-card-title">{video.title}</span>
                            <div className="picker-card-meta">
                              {video.program && (
                                <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                                  {video.program}
                                </span>
                              )}
                              {video.release && (
                                <span className="release-badge" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                                  {t("playlists.releaseBadge", { release: video.release })}
                                </span>
                              )}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="picker-card-add"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAddVideo(video);
                            }}
                            title={t("playlists.addShort")}
                          >
                            <Icon name="add" size={16} />
                          </button>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
  );
}
