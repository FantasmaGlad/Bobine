"use client";

import React from "react";
import type { useUploadManager } from "@/lib/UploadManager";
import { phaseLabelKey } from "@/lib/uploadFlow";
import { formatEta, formatQueueSuffix, KIND_LABEL_KEYS } from "./uploadText";

type Task = ReturnType<typeof useUploadManager>["uploads"][number];
type Translate = (key: string, vars?: Record<string, string | number>) => string;

function ProcessingDetail({ t, task }: { t: Translate; task: Task }) {
  return (
      <>
        {" — "}
        {t(phaseLabelKey("processing"))}{" : "}
        {task.stage === "normalizing" && typeof task.progressPercent === "number" ? (
          <>
            {t("uploadManager.reencoding", { percent: task.progressPercent })}
            {typeof task.etaSeconds === "number" ? (
              ` — ${formatEta(task.etaSeconds)}`
            ) : typeof task.estimatedSeconds === "number" ? (
              ` — ${formatEta(task.estimatedSeconds)} (estimation)`
            ) : null}
            {task.speed && ` (${task.speed})`}
          </>
        ) : (
          <>
            {task.stageLabel ?? t("common.processing")}
            {task.stage === "normalizing" && typeof task.estimatedSeconds === "number" &&
              ` — ${formatEta(task.estimatedSeconds)} (estimation)`}
          </>
        )}
        {formatQueueSuffix(task.queuePosition, task.queueEtaSeconds)}
      </>
  );
}

export default function UploadTaskDetail({ t, task }: { t: Translate; task: Task }) {
  return (
    <span style={{ color: "var(--text-dim)", fontSize: "0.72rem" }}>
      {t(KIND_LABEL_KEYS[task.kind])}
      {task.status === "uploading" && (
        <>{" — "}{t(phaseLabelKey(task.phase ?? "sending"))}</>
      )}
      {task.status === "processing" && <ProcessingDetail t={t} task={task} />}
    </span>
  );
}
