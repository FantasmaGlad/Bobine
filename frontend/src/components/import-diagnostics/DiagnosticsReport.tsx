import Icon from "@/components/Icon";
import { formatAge, isBlockError, problemKeys, type ImportDiagnostics } from "@/lib/importDiagnostics";
import { blockErrorText, diagnosticsRows, type Row } from "./diagnosticsRows";

type T = (key: string, params?: Record<string, string | number>) => string;

function Problems({ report, t }: { report: ImportDiagnostics; t: T }) {
  const problems = problemKeys(report.problems);
  if (problems.length === 0) {
    return (
      <p style={{ color: "var(--accent-success-text)", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "6px" }}>
        <Icon name="check" size={16} color="var(--accent-success-text)" /> {t("settingsPage.importDiag.allGood")}
      </p>
    );
  }
  return (
    <ul role="alert" style={{ margin: "0 0 12px", paddingLeft: "18px", color: "var(--accent-warning-text)", fontSize: "0.88rem" }}>
      {problems.map((key) => <li key={key}>{t(key)}</li>)}
    </ul>
  );
}

function DiagnosticRow({ row }: { row: Row }) {
  return (
    <div style={{ display: "flex", gap: "8px", alignItems: "flex-start", fontSize: "0.88rem" }}>
      <Icon name={row.ok ? "check" : "warning"} size={16} color={row.ok ? "var(--accent-success-text)" : "var(--accent-warning-text)"} />
      <div style={{ minWidth: 0 }}>
        <strong style={{ color: "var(--text-main)" }}>{row.label}</strong>
        <span style={{ color: "var(--text-muted)" }}> — {row.value}</span>
        {row.hint && <div style={{ color: "var(--text-dim)", fontSize: "0.76rem", overflowWrap: "anywhere" }}>{row.hint}</div>}
      </div>
    </div>
  );
}

function Jobs({ jobs, t }: { jobs: ImportDiagnostics["jobs"]; t: T }) {
  if (isBlockError(jobs)) return <span style={{ color: "var(--text-muted)" }}> — {blockErrorText(jobs.error, t)}</span>;
  if (jobs.active.length === 0) return <span style={{ color: "var(--text-muted)" }}> — {t("settingsPage.importDiag.noJobs")}</span>;
  return (
    <ul style={{ margin: "4px 0 0", paddingLeft: "18px", color: "var(--text-muted)" }}>
      {jobs.active.map((job) => (
        <li key={job.id}>
          {t("settingsPage.importDiag.jobLine", {
            kind: job.kind ?? "?", stage: job.stage, age: formatAge(job.age_seconds), idle: formatAge(job.idle_seconds),
          })}
        </li>
      ))}
    </ul>
  );
}

export default function DiagnosticsReport({ report, t }: { report: ImportDiagnostics; t: T }) {
  return (
    <div data-testid="import-diagnostics">
      <Problems report={report} t={t} />
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {diagnosticsRows(report, t).map((row) => <DiagnosticRow key={row.label} row={row} />)}
        <div style={{ fontSize: "0.88rem" }}>
          <strong style={{ color: "var(--text-main)" }}>{t("settingsPage.importDiag.jobs")}</strong>
          <Jobs jobs={report.jobs} t={t} />
        </div>
      </div>
    </div>
  );
}
