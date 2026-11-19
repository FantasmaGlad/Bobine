"use client";

import React from "react";
import type { useUploadManager } from "@/lib/UploadManager";

type Task = ReturnType<typeof useUploadManager>["uploads"][number];

export default function UploadTaskBars({ task }: { task: Task }) {
  return (
    <>
    {task.status === "uploading" && (
      <div style={{ height: "3px", background: "var(--border-color)", borderRadius: "2px" }}>
        <div
          style={{
            height: "100%",
            width: `${task.progress}%`,
            background: "var(--accent-primary)",
            borderRadius: "2px",
            transition: "width 0.2s",
          }}
        />
      </div>
    )}
    {task.status === "processing" && (
      <div style={{ height: "3px", background: "var(--border-color)", borderRadius: "2px", overflow: "hidden" }}>
        {task.stage === "normalizing" && typeof task.progressPercent === "number" ? (
          <div
            style={{
              height: "100%",
              width: `${task.progressPercent}%`,
              background: "var(--accent-primary)",
              borderRadius: "2px",
              transition: "width 0.4s",
            }}
          />
        ) : (
          <div className="olc-indeterminate-bar" style={{ background: "var(--accent-primary)" }} />
        )}
      </div>
    )}
    </>
  );
}
