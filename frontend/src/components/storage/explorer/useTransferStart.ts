"use client";

import { useState } from "react";
import { encodeKey, storageRequest } from "@/lib/storage/request";
import { type BrowseEntry, type TransferKind, type TransferStart } from "@/lib/storage/types";
import { storageErrorText, type StorageCtx } from "../common";

interface Inputs {
  volumeKey: string;
  registered: boolean;
  chosen: BrowseEntry[];
  kind: TransferKind;
  clearSelection: () => void;
  onJob: (jobId: string, mode: "import" | "index") => void;
  onLibraryChanged: () => void;
  ctx: StorageCtx;
}

export function useTransferStart({ volumeKey, registered, chosen, kind, clearSelection, onJob, onLibraryChanged, ctx: { t, lang, notify } }: Inputs) {
  const [busy, setBusy] = useState(false);
  const start = async (mode: "import" | "index") => {
    if (chosen.length === 0) return;
    setBusy(true);
    try {
      if (mode === "index" && !registered) {
        const reg = await storageRequest(`/volumes/${encodeKey(volumeKey)}/library`, { body: {} });
        if (!reg.ok) {
          notify(storageErrorText(reg.error, t, lang), "error");
          return;
        }
        notify(t("storage.extension.started"), "success");
        onLibraryChanged();
      }
      const result = await storageRequest<TransferStart>(`/volumes/${encodeKey(volumeKey)}/${mode}`, {
        body: { entries: chosen.map((e) => ({ path: e.path })), kind },
      });
      if (!result.ok) {
        notify(storageErrorText(result.error, t, lang), "error");
        return;
      }
      if (result.data.job_id) {
        onJob(result.data.job_id, mode);
        clearSelection();
      } else {
        notify(t("storage.job.doneNone"), "warning");
      }
    } finally {
      setBusy(false);
    }
  };

  return { busy, start };
}
