"use client";

import type { UpdateInfo } from "../types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export default function CurrentVersionRow({ t, updateInfo }: { t: Translate; updateInfo: UpdateInfo | null }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
      <span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>
        {t("settingsPage.currentVersion")} :
      </span>
      <span className="update-badge">
        <strong>{updateInfo?.current_version ?? "…"}</strong>
        {updateInfo?.current_commit && updateInfo.current_commit !== "unknown" && (
          <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "0.75rem", opacity: 0.8 }}>
            ({updateInfo.current_commit})
          </span>
        )}
      </span>
      {updateInfo?.checked_at && (
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "auto" }}>
          {t("settingsPage.lastChecked")} : {new Date(updateInfo.checked_at).toLocaleTimeString()}
        </span>
      )}
    </div>
  );
}
