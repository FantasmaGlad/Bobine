"use client";

import { useMemo, useState } from "react";
import { selectableEntries, suggestKind, toggleSelection } from "@/lib/storage/browse";
import { type BrowseEntry, type TransferKind } from "@/lib/storage/types";

export function useExplorerSelection(entries: BrowseEntry[]) {
  const [selected, setSelected] = useState<Record<string, BrowseEntry>>({});
  const [kind, setKind] = useState<TransferKind>("video");
  const [kindTouched, setKindTouched] = useState(false);

  const chosen = useMemo(() => Object.values(selected), [selected]);
  const suggested = !kindTouched && chosen.length ? suggestKind(chosen) : null;
  if (suggested && suggested !== kind) setKind(suggested);

  const toggle = (entry: BrowseEntry) =>
    setSelected((prev) => {
      const next = { ...prev };
      if (toggleSelection(Object.keys(prev), entry.path).includes(entry.path)) next[entry.path] = entry;
      else delete next[entry.path];
      return next;
    });

  const selectable = selectableEntries(entries);
  const allSelected = selectable.length > 0 && selectable.every((e) => selected[e.path]);
  const toggleAll = () =>
    setSelected((prev) => {
      const next = { ...prev };
      for (const entry of selectable) {
        if (allSelected) delete next[entry.path];
        else next[entry.path] = entry;
      }
      return next;
    });

  return { selected, setSelected, chosen, kind, setKind, setKindTouched, toggle, selectable, allSelected, toggleAll };
}
