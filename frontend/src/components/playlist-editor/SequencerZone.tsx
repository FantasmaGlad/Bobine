"use client";

import React from "react";
import Icon from "@/components/Icon";
import type { usePlaylistSequencer } from "@/lib/usePlaylistSequencer";
import SequenceItemActions from "./SequenceItemActions";

type Sequencer<Item> = ReturnType<typeof usePlaylistSequencer<Item>>;

interface SequencerZoneProps<Item> {
  isMobile: boolean;
  items: Item[];
  sequencer: Sequencer<Item>;
  itemKey: (item: Item, index: number) => string;
  renderInfo: (item: Item, index: number) => React.ReactNode;
  empty: { title: string; hint: string };
  actionLabels: { up: string; down: string; remove: string };
  actionsStyle: React.CSSProperties;
}

export default function SequencerZone<Item>({ isMobile, items, sequencer, itemKey, renderInfo, empty, actionLabels, actionsStyle }: SequencerZoneProps<Item>) {
  const {
    draggedIndex, dragSource, dragOverIndex, setDragOverIndex, remove, moveUp, moveDown,
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
      {items.length === 0 ? (
        <div className="empty-playlist-placeholder">
          <Icon name="playlist_add" size={32} color="var(--border-focus)" />
          <span>{empty.title}</span>
          <span style={{ fontSize: "0.75rem", opacity: 0.7 }}>{empty.hint}</span>
        </div>
      ) : (
        items.map((item, index) => {
          const isDragged = draggedIndex === index && dragSource === "sequencer";
          const isOver = dragOverIndex === index;
          return (
            <div
              key={itemKey(item, index)}
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
              {renderInfo(item, index)}
              <SequenceItemActions index={index} count={items.length} style={actionsStyle} labels={actionLabels}
                onMoveUp={moveUp} onMoveDown={moveDown} onRemove={remove} />
            </div>
          );
        })
      )}
    </div>
  );
}
