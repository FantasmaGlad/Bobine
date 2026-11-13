"use client";
import React from "react";
import Icon from "@/components/Icon";
import type { UpdateInfo } from "./types";

interface StoreUpdatePanelProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  updateInfo: UpdateInfo | null;
  storeBusy: boolean;
  handleStoreAction: (action: "start" | "complete" | "open") => void;
}

export default function StoreUpdatePanel({ t, updateInfo, storeBusy, handleStoreAction }: StoreUpdatePanelProps) {
  return (
              <div className="olc-anim-in" style={{ display: "flex", flexDirection: "column", gap: "12px", width: "100%", maxWidth: "620px" }}>
                <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeManagedHint")}</p>
                <div className="update-card-banner" style={{ borderLeft: "4px solid var(--accent-text)", boxShadow: "var(--shadow-sm)", display: "flex", flexDirection: "column", gap: "10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700 }}>
                    <Icon
                      name={updateInfo?.store?.state === "available" || updateInfo?.store?.state === "downloaded" ? "system_update" : updateInfo?.store?.state === "failed" ? "error" : "check_circle"}
                      size={18}
                    />
                    <span>
                      {updateInfo?.store?.state === "none" && t("settingsPage.storeUpToDate")}
                      {updateInfo?.store?.state === "available" && `${t("settingsPage.storeAvailable")}${updateInfo.store.version_code ? ` (build ${updateInfo.store.version_code})` : ""}`}
                      {updateInfo?.store?.state === "downloading" && t("settingsPage.storeDownloading")}
                      {updateInfo?.store?.state === "downloaded" && t("settingsPage.storeDownloaded")}
                      {updateInfo?.store?.state === "installing" && t("settingsPage.storeInstalling")}
                      {updateInfo?.store?.state === "failed" && t("settingsPage.storeFailed")}
                      {(!updateInfo?.store || updateInfo.store.state === "unavailable") && (updateInfo?.store?.message || t("settingsPage.storeUnavailable"))}
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                    {updateInfo?.store?.state === "available" && (
                      <button type="button" className="btn btn-primary" disabled={storeBusy} onClick={() => handleStoreAction("start")}>
                        <Icon name="system_update" size={16} /> {t("settingsPage.storeUpdateButton")}
                      </button>
                    )}
                    {updateInfo?.store?.state === "downloaded" && (
                      <button type="button" className="btn btn-primary" disabled={storeBusy} onClick={() => handleStoreAction("complete")}>
                        <Icon name="restart_alt" size={16} /> {t("settingsPage.storeRestartButton")}
                      </button>
                    )}
                    <button type="button" className="btn btn-secondary" disabled={storeBusy} onClick={() => handleStoreAction("open")}>
                      <Icon name="storefront" size={16} /> {t("settingsPage.storeOpenButton")}
                    </button>
                  </div>
                </div>
                <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeAutoHint")}</p>
                <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeBetaHint")}</p>
              </div>
  );
}
