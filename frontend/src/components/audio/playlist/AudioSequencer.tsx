"use client";
import React from "react";
import Icon from "@/components/Icon";
import SequenceItemActions from "@/components/playlist-editor/SequenceItemActions";
import SequencerTrackInfo from "./SequencerTrackInfo";
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
                          <SequencerTrackInfo t={t} item={item} backgrounds={backgrounds} onBackground={(id) => handleSetTrackBackground(index, id)} />
                          <SequenceItemActions index={index} count={playlistItems.length} style={{ display: "flex", gap: "4px", flexShrink: 0 }}
                            labels={{ up: t("audioPlaylists.moveUp"), down: t("audioPlaylists.moveDown"), remove: t("audioPlaylists.remove") }}
                            onMoveUp={handleMoveUp} onMoveDown={handleMoveDown} onRemove={handleRemoveTrack} />
                        </div>
                      );
                    })
                  )}
                </div>
  );
}
