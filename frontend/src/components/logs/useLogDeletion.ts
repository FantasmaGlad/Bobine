"use client";

import { useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";

export function useLogDeletion() {
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(false);

  const remove = (path: string, confirmMessage: string, onDone: () => void) => {
    if (!window.confirm(confirmMessage)) return;
    setDeleting(true);
    setDeleteError(false);
    fetch(getApiUrl(path), { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("delete failed");
        onDone();
      })
      .catch(() => setDeleteError(true))
      .finally(() => setDeleting(false));
  };

  return { deleting, deleteError, remove };
}
