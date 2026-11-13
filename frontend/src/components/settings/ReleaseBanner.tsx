"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import MarkdownView from "@/components/MarkdownView";
import { formatBinarySize } from "@/lib/format";
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
  
                    {updateInfo.release_notes && (
                      <div>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ marginBottom: "8px" }}
                          onClick={() => setShowReleaseNotes((v) => !v)}
                        >
                          <Icon name={showReleaseNotes ? "expand_less" : "expand_more"} size={16} />
                          {t("settingsPage.releaseNotes")}
                        </button>
                        {showReleaseNotes && (
                          <div className="update-notes-box olc-anim-in">
                            <MarkdownView content={updateInfo.release_notes} />
                          </div>
                        )}
                      </div>
                    )}
  
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "4px" }}>
                      {updateInfo.can_auto_apply ? (
                        <button
                          type="button"
                          className="btn btn-primary"
                          style={{ height: "42px", padding: "0 20px", display: "inline-flex", alignItems: "center", gap: "8px" }}
                          onClick={handleApplyUpdate}
                          disabled={applyingUpdate}
                        >
                          {applyingUpdate ? (
                            <>
                              <Icon name="sync" size={16} className="olc-spin" />
                              {t("settingsPage.applyingUpdate")}
                            </>
                          ) : (
                            <>
                              <Icon name="download" size={16} />
                              {updateInfo.is_downgrade ? t("settingsPage.applyDowngrade") : t("settingsPage.applyUpdate")}
                            </>
                          )}
                        </button>
                      ) : (
                        <a
                          href={updateInfo.download_url || updateInfo.html_url || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-primary"
                          style={{ height: "42px", padding: "0 20px", display: "inline-flex", alignItems: "center", gap: "8px", textDecoration: "none" }}
                        >
                          <Icon name="download" size={16} />
                          {updateInfo.asset_name
                            ? `${t("settingsPage.downloadUpdate")} (${updateInfo.asset_name}${updateInfo.asset_size ? ` - ${formatBinarySize(updateInfo.asset_size)}` : ""})`
                            : t("settingsPage.downloadUpdate")}
                        </a>
                      )}
                    </div>
                  </div>
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
