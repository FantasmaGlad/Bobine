"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import DiagnosticsReport from "./import-diagnostics/DiagnosticsReport";
import { useImportDiagnostics } from "./import-diagnostics/useImportDiagnostics";

export default function ImportDiagnosticsPanel() {
  const { t } = useAppSettings();
  const { report, loading, failed, copied, load, copy } = useImportDiagnostics();

  return (
    <section className="live-block" id="section-import-diagnostics">
      <h3><Icon name="troubleshoot" size={18} /> {t("settingsPage.importDiag.title")}</h3>
      <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.importDiag.hint")}</p>
      {failed && (
        <p role="alert" style={{ color: "var(--accent-error-text)", fontSize: "0.88rem" }}>{t("settingsPage.importDiag.loadError")}</p>
      )}
      {report && <DiagnosticsReport report={report} t={t} />}
      <div style={{ display: "flex", gap: "10px", marginTop: "14px", flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
          <Icon name="refresh" size={18} /> {loading ? t("settingsPage.importDiag.refreshing") : t("settingsPage.importDiag.refresh")}
        </button>
        {report && (
          <button type="button" className="btn btn-secondary" onClick={() => void copy()}>
            <Icon name="content_copy" size={18} /> {copied ? t("settingsPage.importDiag.copied") : t("settingsPage.importDiag.copy")}
          </button>
        )}
      </div>
    </section>
  );
}
