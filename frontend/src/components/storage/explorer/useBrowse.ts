"use client";

import { useCallback, useEffect, useState } from "react";
import { encodeKey, storageRequest } from "@/lib/storage/request";
import { type BrowseEntry, type BrowseResult } from "@/lib/storage/types";
import { storageErrorText, type StorageCtx } from "../common";

const PAGE = 200;

export function useBrowse(volumeKey: string, { t, lang, notify }: StorageCtx) {
  const [path, setPath] = useState("");
  const [entries, setEntries] = useState<BrowseEntry[]>([]);
  const [meta, setMeta] = useState<Pick<BrowseResult, "total" | "truncated" | "skipped_links">>({ total: 0, truncated: false, skipped_links: 0 });
  const [loading, setLoading] = useState(true);

  const fetchPage = useCallback(
    (target: string, offset: number) => {
      const query = new URLSearchParams({ path: target, offset: String(offset), limit: String(PAGE), media_only: "true" });
      return storageRequest<BrowseResult>(`/volumes/${encodeKey(volumeKey)}/browse?${query}`).then((result) => {
        setLoading(false);
        if (!result.ok) {
          notify(storageErrorText(result.error, t, lang), "error");
          return;
        }
        setEntries((prev) => (offset === 0 ? result.data.entries : [...prev, ...result.data.entries]));
        setMeta({ total: result.data.total, truncated: result.data.truncated, skipped_links: result.data.skipped_links });
      });
    },
    [volumeKey, notify, t, lang],
  );

  const loadMore = () => {
    setLoading(true);
    void fetchPage(path, entries.length);
  };

  const [shownPath, setShownPath] = useState(path);
  if (shownPath !== path) {
    setShownPath(path);
    setLoading(true);
  }

  useEffect(() => {
    void fetchPage(path, 0);
  }, [fetchPage, path]);

  const goTo = (target: string) => {
    setPath(target);
    setEntries([]);
  };

  return { path, entries, meta, loading, loadMore, goTo };
}
