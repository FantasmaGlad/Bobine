"use client";

import { getApiUrl } from "@/lib/apiUrl";

export default function TechnicalToolbar({ t, fetchTechnical, clearTechnicalLog, deleting, technicalLog }: {
  t: (key: string) => string;
  fetchTechnical: () => void;
  clearTechnicalLog: () => void;
  deleting: boolean;
  technicalLog: string;
}) {
  return (
    <div className="toolbar-filters" style={{ gap: "8px" }}>
      <button className="btn btn-secondary" onClick={fetchTechnical}>
        {t("logs.refresh")}
      </button>
      <button className="btn btn-danger" disabled={deleting || !technicalLog} onClick={clearTechnicalLog}>
        {t("logs.clearLogs")}
      </button>
      <a href={getApiUrl("/logs/technical/download")} download className="btn btn-secondary">
        {t("logs.downloadFullLog")}
      </a>
    </div>
  );
}
