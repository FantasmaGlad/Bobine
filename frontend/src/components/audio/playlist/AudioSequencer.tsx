"use client";
import React from "react";
import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { formatMediaDuration } from "@/lib/format";
import type { BackgroundSummary, PlaylistDraftItem, Sequencer } from "./types";

interface AudioSequencerProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  isMobile: boolean;
  playlistItems: PlaylistDraftItem[];
  backgrounds: BackgroundSummary[];
  sequencer: Sequencer;
  handleSetTrackBackground: (index: number, backgroundId: number | null) => void;
}

export default function AudioSequencer({ t, isMobile, playlistItems, backgrounds, sequencer, handleSetTrackBackground }: AudioSequencerProps) {
  const {
    draggedIndex, dragSource, dragOverIndex, setDragOverIndex, remove: handleRemoveTrack, moveUp: handleMoveUp, moveDown: handleMoveDown,
    handleDragStart, handleDragOver, handleDragLeave, handleDrop, handleDropOnEmptyZone, resetDragState,
  } = sequencer;
  return (
                <div
                  className={`drag-drop-zone ${dragOverIndex === -1 ? "drag-over" : ""}`}
                  style={isMobile ? { minHeight: "80px", maxHeight: "320px" } : undefined}
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (dragSource === "library") setDragOverIndex(-1);
                  }}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDropOnEmptyZone}
                >
                  {playlistItems.length === 0 ? (
                    <div className="empty-playlist-placeholder">
                      <Icon name="playlist_add" size={32} color="var(--border-focus)" />
                      <span>{t("audioPlaylists.emptySequencer")}</span>
                      <span style={{ fontSize: "0.75rem", opacity: 0.7 }}>{t("audioPlaylists.emptySequencerHint")}</span>
                    </div>
                  ) : (
                    playlistItems.map((item, index) => {
                      const isDragged = draggedIndex === index && dragSource === "sequencer";
                      const isOver = dragOverIndex === index;
                      return (
                        <div
                          key={`${item.track.id}-${index}`}
                          className={`playlist-drag-item ${isDragged ? "dragging" : ""} ${isOver ? "drag-over-item" : ""}`}
                          draggable={!isMobile}
                          onDragStart={(e) => handleDragStart(e, index, "sequencer")}
                          onDragOver={(e) => handleDragOver(e, index)}
                          onDragLeave={handleDragLeave}
                          onDrop={(e) => handleDrop(e, index)}
                          onDragEnd={resetDragState}
                        >
                          {!isMobile && <div className="drag-handle"><Icon name="drag_indicator" size={16} /></div>}
                          <span style={{ fontWeight: 800, color: "var(--text-muted)", fontSize: "0.85rem", width: "16px" }}>
                            {index + 1}
                          </span>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--text-main)", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                              {item.track.title}
                            </div>
                            <div style={{ display: "flex", gap: "6px", alignItems: "center", marginTop: "1px" }}>
                              {item.track.course_program && (
                                <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
                                  {item.track.course_program}
                                </span>
                              )}
                              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                                {item.track.course_title} · {formatMediaDuration(item.track.duration_seconds)}
                              </span>
                            </div>
                            <div onClick={(e) => e.stopPropagation()}>
                              <ResponsiveSelect
                                value={item.backgroundId != null ? String(item.backgroundId) : ""}
                                onChange={(value) => handleSetTrackBackground(index, value ? Number(value) : null)}
                                placeholder={t("audioPlaylists.trackBackgroundNone")}
                                title={t("audioPlaylists.trackBackgroundLabel")}
                                style={{ minHeight: "22px", fontSize: "0.68rem", padding: "0 4px", marginTop: "3px", maxWidth: "180px" }}
                                options={backgrounds.map((bg) => ({ value: String(bg.id), label: bg.title }))}
                              />
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "4px", flexShrink: 0 }}>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleMoveUp(index)}
                              disabled={index === 0}
                              title={t("audioPlaylists.moveUp")}
                            >
                              <Icon name="arrow_upward" size={14} />
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleMoveDown(index)}
                              disabled={index === playlistItems.length - 1}
                              title={t("audioPlaylists.moveDown")}
                            >
                              <Icon name="arrow_downward" size={14} />
                            </button>
                            <button
                              type="button"
                              className="btn btn-danger"
                              style={{ width: "24px", height: "24px", padding: 0, borderRadius: "50%", fontSize: "0.8rem" }}
                              onClick={() => handleRemoveTrack(index)}
                              title={t("audioPlaylists.remove")}
                            >
                              <Icon name="close" size={14} />
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
  );
}
