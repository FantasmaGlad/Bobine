"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import UpdateAvailableCard from "./release/UpdateAvailableCard";
import type { UpdateInfo } from "./types";

interface ReleaseBannerProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  updateInfo: UpdateInfo;
  applyingUpdate: boolean;
  handleApplyUpdate: () => void;
}
export default function ReleaseBanner({ t, updateInfo, applyingUpdate, handleApplyUpdate }: ReleaseBannerProps) {
  const [showReleaseNotes, setShowReleaseNotes] = useState(false);
  return (
              <div className="olc-anim-in" style={{ marginTop: "4px" }}>
                {updateInfo.has_update ? (
                  <UpdateAvailableCard t={t} updateInfo={updateInfo} applyingUpdate={applyingUpdate} handleApplyUpdate={handleApplyUpdate}
                    showReleaseNotes={showReleaseNotes} setShowReleaseNotes={setShowReleaseNotes} />
                ) : updateInfo.online ? (
                  <div
                    className="update-card-banner"
                    style={{
                      borderLeft: "4px solid var(--accent-text)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="update-badge success">
                        <Icon name="check_circle" size={14} />
                        {t("settingsPage.upToDate")}
                      </span>
                      <span style={{ fontSize: "0.9rem", color: "var(--text-main)" }}>
                        {t("settingsPage.upToDateDetail")}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div
                    className="update-card-banner"
                    style={{ borderLeft: "4px solid var(--border-color)" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-muted)" }}>
                      <Icon name={updateInfo.error_code === "offline" || !updateInfo.error_code ? "wifi_off" : "info"} size={16} />
                      <span style={{ fontSize: "0.85rem" }}>
                        {updateInfo.message || t("settingsPage.updateError")}
                      </span>
                    </div>
                  </div>
                )}
              </div>
  );
}
