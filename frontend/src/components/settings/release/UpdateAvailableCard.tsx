"use client";

import Icon from "@/components/Icon";
import type { UpdateInfo } from "../types";
import ReleaseAction from "./ReleaseAction";
import ReleaseNotesToggle from "./ReleaseNotesToggle";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export default function UpdateAvailableCard({ t, updateInfo, applyingUpdate, handleApplyUpdate, showReleaseNotes, setShowReleaseNotes }: {
  t: Translate; updateInfo: UpdateInfo; applyingUpdate: boolean; handleApplyUpdate: () => void;
  showReleaseNotes: boolean; setShowReleaseNotes: (update: (v: boolean) => boolean) => void;
}) {
  return (
  <div
    className="update-card-banner"
    style={{
      borderLeft: "4px solid var(--accent-text)",
      boxShadow: "var(--shadow-sm)",
    }}
  >
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <span className="update-badge alert">
          <Icon name="campaign" size={14} />
          {updateInfo.is_downgrade ? t("settingsPage.downgradeAvailable") : t("settingsPage.updateAvailable")}
        </span>
        <strong style={{ fontSize: "0.95rem" }}>{updateInfo.latest_version}</strong>
      </div>
      {updateInfo.html_url && (
        <a
          href={updateInfo.html_url}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-secondary btn-sm"
          style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "4px" }}
        >
          <Icon name="open_in_new" size={14} /> {t("settingsPage.viewOnGithub")}
        </a>
      )}
    </div>
  
    <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--text-main)" }}>
      {updateInfo.is_downgrade
        ? t("settingsPage.downgradeDetail")
        : updateInfo.release_title || t("settingsPage.updateAvailableDetail")}
    </p>
  
      {updateInfo.release_notes && <ReleaseNotesToggle notes={updateInfo.release_notes} label={t("settingsPage.releaseNotes")}
        showReleaseNotes={showReleaseNotes} setShowReleaseNotes={setShowReleaseNotes} />}
      <ReleaseAction t={t} updateInfo={updateInfo} applyingUpdate={applyingUpdate} handleApplyUpdate={handleApplyUpdate} />
    </div>
  );
}
