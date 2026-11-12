"use client";

import type React from "react";
import { useState } from "react";

type DragSource = "sequencer" | "library";

export function usePlaylistSequencer<Item>(
  setItems: React.Dispatch<React.SetStateAction<Item[]>>,
  fromLibrary: (id: number) => Item | undefined,
) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [draggedLibraryId, setDraggedLibraryId] = useState<number | null>(null);
  const [dragSource, setDragSource] = useState<DragSource | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const remove = (index: number) => setItems((prev) => prev.filter((_, i) => i !== index));

  const move = (index: number, offset: -1 | 1) =>
    setItems((prev) => {
      const target = index + offset;
      if (target < 0 || target >= prev.length) return prev;
      const copy = [...prev];
      [copy[index], copy[target]] = [copy[target], copy[index]];
      return copy;
    });

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

  const handleDragLeave = () => setDragOverIndex(null);

  const insertAt = (targetIndex: number | null) => {
    if (dragSource === "sequencer" && draggedIndex !== null && targetIndex !== null && draggedIndex !== targetIndex) {
      setItems((prev) => {
        const copy = [...prev];
        const [moved] = copy.splice(draggedIndex, 1);
        copy.splice(targetIndex, 0, moved);
        return copy;
      });
    } else if (dragSource === "library" && draggedLibraryId !== null) {
      const item = fromLibrary(draggedLibraryId);
      if (item) {
        setItems((prev) => {
          const copy = [...prev];
          copy.splice(targetIndex ?? copy.length, 0, item);
          return copy;
        });
      }
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
    draggedIndex,
    dragSource,
    dragOverIndex,
    setDragOverIndex,
    remove,
    moveUp: (index: number) => move(index, -1),
    moveDown: (index: number) => move(index, 1),
    handleDragStart,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleDropOnEmptyZone,
    resetDragState: reset,
  };
}
