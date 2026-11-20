"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import RenditionButton from "./web-rendition/RenditionButton";
import { decodeIssueLabels, useWebRendition } from "./web-rendition/useWebRendition";

const PANEL_STYLE = { marginTop: 12, padding: "12px 14px", border: "1px solid var(--border-color)", borderRadius: "var(--radius-md)", background: "var(--bg-surface-elevated)", display: "flex", flexDirection: "column", gap: 8 } as const;

export default function WebRenditionPanel({ videoId }: { videoId: number }) {
  const { t } = useAppSettings();
  const { state, busy, message, act } = useWebRendition(videoId, t);
  const labels = decodeIssueLabels(state?.web_issues ?? [], t);
  if (!state || labels.length === 0) return null;

  const status = state.web_status;
  return (
    <div className="web-rendition-panel" style={PANEL_STYLE}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
        <Icon name={status === "ready" ? "check_circle" : "devices"} size={18} color={status === "ready" ? "var(--accent-success-text)" : "var(--accent-text)"} />
        {t("webRendition.title")}
      </div>
      <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
        {status === "ready" ? t("webRendition.ready") : t("webRendition.notSafe", { issues: labels.join(", ") })}
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <RenditionButton status={status} busy={busy} act={act} t={t} />
        {status === "error" && <span style={{ color: "var(--accent-error-text)", fontSize: "0.8rem" }}>{t("webRendition.failed")}</span>}
        {message && <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{message}</span>}
      </div>
    </div>
  );
}
