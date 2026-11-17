import React from "react";
import Icon from "@/components/Icon";
import { fsLabel } from "@/lib/storage/advice";
import { formatBytes } from "@/lib/storage/display";
import { FORMAT_STEP_ORDER, refusalKey, stepIcon, type FormatJob } from "@/lib/storage/format";
import { tr, type Lang, type T } from "../common";

type Report = NonNullable<FormatJob["report"]>;

function FormatReport({ report, t, lang }: { report: Report; t: T; lang: Lang }) {
  return (
    <div className="dv-detail-block">
      <div className="fmt-checks">
        {report.checks?.map((c) => (
          <span key={c.id} className="fmt-chip" data-ok={c.ok}><Icon name={c.ok ? "check_circle" : "error"} size={16} />{tr(t, `storage.format.checks.${c.id}`, c.id)}</span>
        ))}
      </div>
      {report.size_bytes != null && <p className="dv-sub">{t("storage.format.resultLine", { fs: fsLabel(report.filesystem), label: report.label ?? "", size: formatBytes(report.size_bytes, lang) })}</p>}
      <p className="dv-sub">{report.health?.available ? t(`storage.format.health.${report.health.status === "ok" ? "ok" : "warn"}`) : t("storage.format.health.unknown")}</p>
      {report.mounted_read_only && <p className="dv-sub">{t("storage.format.readOnlyNote")}</p>}
    </div>
  );
}

interface FormatProgressProps {
  job: FormatJob | null;
  running: boolean;
  pollError: boolean;
  t: T;
  lang: Lang;
}

export default function FormatProgress({ job, running, pollError, t, lang }: FormatProgressProps) {
  const steps = job?.steps ?? FORMAT_STEP_ORDER.map((id) => ({ id, state: "pending" as const }));
  const report = job?.report;
  const outcome = job?.outcome;
  return (
    <div className="dv-detail">
      {running && pollError && <p className="dv-error" role="status">{t("storage.format.connectionLost")}</p>}
      {running && (
        <div className="dv-note dv-note--strong" role="status">
          <Icon name={job?.point_of_no_return ? "lock" : "pending"} size={20} />
          <span>{job?.point_of_no_return ? t("storage.format.noReturn") : t("storage.format.canCancel")}</span>
        </div>
      )}
      {!running && outcome && (
        <div className={outcome === "verified" ? "dv-note dv-note--strong" : "fmt-erase"} role="status">
          <strong>{t(`storage.format.outcomeTitle.${outcome}`)}</strong>
          <span className="dv-sub">{t(`storage.format.outcomeText.${outcome}`)}</span>
          {job?.error && <span className="dv-sub">{tr(t, refusalKey(job.error.code), job.error.message)}</span>}
        </div>
      )}
      <ul className="fmt-steps" aria-label={t("storage.format.stepsTitle")}>
        {steps.map((s) => (
          <li key={s.id} data-state={s.state}>
            <Icon name={stepIcon(s.state)} size={20} />
            <span>{t(`storage.format.steps.${s.id}`)}</span>
          </li>
        ))}
      </ul>
      {!running && report && (report.checks?.length ?? 0) > 0 && <FormatReport report={report} t={t} lang={lang} />}
    </div>
  );
}
