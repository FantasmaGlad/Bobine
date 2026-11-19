"use client";

import type React from "react";
import { useState } from "react";
import { insertItem, moveItem, reorderItem } from "./sequenceOps";

type DragSource = "sequencer" | "library";

function useDragState() {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [draggedLibraryId, setDraggedLibraryId] = useState<number | null>(null);
  const [dragSource, setDragSource] = useState<DragSource | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const reset = () => {
    setDraggedIndex(null);
    setDraggedLibraryId(null);
    setDragSource(null);
    setDragOverIndex(null);
  };

  const handleDragStart = (e: React.DragEvent, indexOrId: number, source: DragSource) => {
    setDragSource(source);
    if (source === "sequencer") setDraggedIndex(indexOrId);
    else setDraggedLibraryId(indexOrId);
    e.dataTransfer.setData("text/plain", indexOrId.toString());
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  return {
    draggedIndex, draggedLibraryId, dragSource, dragOverIndex, setDragOverIndex, reset,
    handleDragStart, handleDragOver, handleDragLeave: () => setDragOverIndex(null),
  };
}

export function usePlaylistSequencer<Item>(
  setItems: React.Dispatch<React.SetStateAction<Item[]>>,
  fromLibrary: (id: number) => Item | undefined,
) {
  const drag = useDragState();
  const { draggedIndex, draggedLibraryId, dragSource, reset } = drag;
  const remove = (index: number) => setItems((prev) => prev.filter((_, i) => i !== index));
  const move = (index: number, offset: -1 | 1) => setItems((prev) => moveItem(prev, index, offset));

  const insertAt = (targetIndex: number | null) => {
    if (dragSource === "sequencer" && draggedIndex !== null && targetIndex !== null && draggedIndex !== targetIndex) {
      setItems((prev) => reorderItem(prev, draggedIndex, targetIndex));
    } else if (dragSource === "library" && draggedLibraryId !== null) {
      const item = fromLibrary(draggedLibraryId);
      if (item) setItems((prev) => insertItem(prev, item, targetIndex));
    }
    reset();
  };

  const handleDrop = (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    insertAt(targetIndex);
  };

  const handleDropOnEmptyZone = (e: React.DragEvent) => {
    e.preventDefault();
    if (dragSource === "library") insertAt(null);
    else reset();
  };

  return {
    draggedIndex, dragSource, dragOverIndex: drag.dragOverIndex, setDragOverIndex: drag.setDragOverIndex, remove,
    moveUp: (index: number) => move(index, -1), moveDown: (index: number) => move(index, 1),
    handleDragStart: drag.handleDragStart, handleDragOver: drag.handleDragOver, handleDragLeave: drag.handleDragLeave,
    handleDrop, handleDropOnEmptyZone, resetDragState: reset,
  };
}
