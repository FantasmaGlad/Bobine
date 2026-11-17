"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import UploadFloatingPanel from "@/components/uploads/UploadFloatingPanel";
import { CHUNKED_KINDS, maxConcurrentUploads } from "@/lib/uploads/request";
import { runChunkedUpload, runMultipartUpload } from "@/lib/uploads/transports";
import type { PendingUploadSpec, TaskControls, UploadTask } from "@/lib/uploads/types";
import { useJobPolling } from "@/lib/uploads/useJobPolling";

interface UploadManagerContextValue {
  uploads: UploadTask[];
  addUploads: (specs: PendingUploadSpec[]) => void;
  cancelUpload: (id: string) => void;
  clearCompleted: () => void;
}

const UploadManagerContext = createContext<UploadManagerContextValue | null>(null);

function uuid(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

const ACTIVE: ReadonlySet<UploadTask["status"]> = new Set<UploadTask["status"]>(["uploading", "pending", "processing"]);

function useUploadList() {
  const [uploads, setUploads] = useState<UploadTask[]>([]);
  const uploadsRef = useRef<UploadTask[]>([]);
  const replace = useCallback((change: (prev: UploadTask[]) => UploadTask[]) => {
    setUploads((prev) => {
      const next = change(prev);
      uploadsRef.current = next;
      return next;
    });
  }, []);
  const updateTask = useCallback(
    (id: string, patch: Partial<UploadTask>) => replace((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t))),
    [replace],
  );
  const removeTask = useCallback((id: string) => replace((prev) => prev.filter((t) => t.id !== id)), [replace]);
  return { uploads, uploadsRef, replace, updateTask, removeTask };
}

export function UploadManagerProvider({ children }: { children: React.ReactNode }) {
  const { uploads, uploadsRef, replace, updateTask, removeTask } = useUploadList();

  const runUpload = useCallback(
    (task: UploadTask, onDone: () => void) => {
      const controls: TaskControls = {
        update: (patch) => updateTask(task.id, patch),
        remove: () => removeTask(task.id),
        done: onDone,
      };
      const multipart = () => runMultipartUpload(task, controls);
      if (CHUNKED_KINDS.has(task.kind) && task.file) {
        runChunkedUpload(task, controls, multipart);
        return;
      }
      multipart();
    },
    [updateTask, removeTask],
  );

  const fillSlotsRef = useRef<() => void>(() => {});
  const fillSlots = useCallback(() => {
    const activeCount = uploadsRef.current.filter((t) => t.status === "uploading").length;
    const slotsFree = maxConcurrentUploads() - activeCount;
    if (slotsFree <= 0) return;
    const toStart = uploadsRef.current.filter((t) => t.status === "pending").slice(0, slotsFree);
    toStart.forEach((task) => runUpload(task, () => fillSlotsRef.current()));
  }, [runUpload, uploadsRef]);
  useEffect(() => {
    fillSlotsRef.current = fillSlots;
  }, [fillSlots]);

  const addUploads = useCallback(
    (specs: PendingUploadSpec[]) => {
      const newTasks: UploadTask[] = specs.map((spec) => ({ ...spec, id: uuid(), status: "pending", progress: 0 }));
      replace((prev) => [...prev, ...newTasks]);
      setTimeout(fillSlots, 0);
    },
    [fillSlots, replace],
  );

  const cancelUpload = useCallback((id: string) => {
    const task = uploadsRef.current.find((t) => t.id === id);
    if (!task) return;
    if (task.jobId) {
      fetch(getApiUrl(`/import-jobs/${task.jobId}`), { method: "DELETE" }).catch((e) => {
        console.error("Erreur lors de l'annulation de la tâche sur le serveur:", e);
      });
    }
    if (task.status === "uploading" && (task.xhr || task.abort)) {
      if (task.xhr) task.xhr.abort();
      else task.abort?.();
    } else {
      removeTask(id);
    }
  }, [uploadsRef, removeTask]);

  const clearCompleted = useCallback(() => replace((prev) => prev.filter((t) => ACTIVE.has(t.status))), [replace]);

  useJobPolling(uploadsRef, updateTask, removeTask);

  return (
    <UploadManagerContext.Provider value={{ uploads, addUploads, cancelUpload, clearCompleted }}>
      {children}
      <UploadFloatingPanel />
    </UploadManagerContext.Provider>
  );
}

export function useUploadManager(): UploadManagerContextValue {
  const ctx = useContext(UploadManagerContext);
  if (!ctx) throw new Error("useUploadManager must be used inside <UploadManagerProvider>");
  return ctx;
}
