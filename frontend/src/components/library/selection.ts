"use client";

import React, { useRef, useState } from "react";

export function useSelection<T extends { id: number }>(items: T[]) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const lastIndex = useRef<number | null>(null);

  const toggle = (id: number) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const setMany = (ids: number[], select: boolean) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (select) next.add(id);
        else next.delete(id);
      }
      return next;
    });

  const allSelected = (ids: number[]) => ids.length > 0 && ids.every((id) => selectedIds.has(id));

  const rangeClick = (e: React.MouseEvent, index: number, id: number) => {
    if (e.shiftKey && lastIndex.current !== null && lastIndex.current !== index) {
      const [a, b] = [lastIndex.current, index].sort((x, y) => x - y);
      setMany(items.slice(a, b + 1).map((item) => item.id), !selectedIds.has(id));
    } else {
      toggle(id);
    }
    lastIndex.current = index;
  };

  const clear = () => setSelectedIds(new Set());

  return { selectedIds, toggle, setMany, allSelected, rangeClick, clear };
}

export type Selection = ReturnType<typeof useSelection>;
