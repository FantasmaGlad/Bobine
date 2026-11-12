"use client";
import { errorMessage } from "@/lib/apiError";

import React, { useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";

const UNINSTALL_PHRASE = "DÉSINSTALLER";
const RESET_DATA_PHRASE = "RÉINITIALISER";
const normalizePhrase = (s: string) => s.trim().toUpperCase().replace(/É/g, "E");

type ToastType = "success" | "error" | "warning";

interface DangerSectionProps {
  hidden: boolean;
  deploymentProfile: string;
  showToast: (message: string, type?: ToastType) => void;
}

export default function DangerSection({ hidden, deploymentProfile, showToast }: DangerSectionProps) {
  const { t } = useAppSettings();
  const [showUninstall, setShowUninstall] = useState(false);
  const [uninstallConfirm, setUninstallConfirm] = useState("");
  const [uninstalling, setUninstalling] = useState(false);
  const [showResetData, setShowResetData] = useState(false);
  const [resetDataConfirm, setResetDataConfirm] = useState("");
  const [resettingData, setResettingData] = useState(false);

  const handleUninstall = async () => {
    setUninstalling(true);
    try {
      const res = await fetch(getApiUrl("/settings/system/uninstall"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: uninstallConfirm }),
      });
      const payload = await res.json().catch(() => ({}));
      if (res.ok) {
        showToast(payload.message || t("settingsPage.uninstallStarted"), "warning");
      } else {
        showToast(errorMessage(payload, t("settingsPage.uninstallError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setUninstalling(false);
      setShowUninstall(false);
      setUninstallConfirm("");
    }
  };

  const resetDataReady = normalizePhrase(resetDataConfirm) === "REINITIALISER";

  const handleResetData = async () => {
    if (!resetDataReady) return;
    setResettingData(true);
    try {
      const res = await fetch(getApiUrl("/settings/system/reset-data"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: resetDataConfirm }),
      });
      if (res.ok) {
        showToast(t("settingsPage.resetDataSuccess"), "success");
        setShowResetData(false);
        setResetDataConfirm("");
      } else {
        const err = await res.json().catch(() => null);
        showToast(errorMessage(err, t("settingsPage.resetDataError")), "error");
      }
    } catch {
      showToast(t("settingsPage.resetDataError"), "error");
    } finally {
      setResettingData(false);
    }
  };

  const uninstallReady = normalizePhrase(uninstallConfirm) === "DESINSTALLER";

  return (
    <>
      <section className="live-block settings-danger" id="section-danger" hidden={hidden}>
        <h3 style={{ margin: "0 0 6px 0" }}>
          <Icon name="warning" size={18} /> {t("settingsPage.dangerSection")}
        </h3>
        <p className="settings-hint" style={{ margin: "0 0 16px 0" }}>
          {t("settingsPage.dangerHint")}
        </p>

        <div className="settings-danger-group">
          <div className="settings-danger-card">
            <h4>
              <Icon name="cleaning_services" size={18} /> {t("settingsPage.resetDataTitle")}
            </h4>
            <p>{t("settingsPage.resetDataHint")}</p>
            <div>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => setShowResetData(true)}
              >
                <Icon name="cleaning_services" size={16} /> {t("settingsPage.resetDataAction")}
              </button>
            </div>
          </div>

          <div className="settings-danger-card">
            <h4>
              <Icon name="delete_forever" size={18} /> {t("settingsPage.uninstallSectionTitle")}
            </h4>
            <p>
              {t(
                deploymentProfile === "windows"
                  ? "settingsPage.uninstallDesktopWindows"
                  : deploymentProfile === "macos"
                  ? "settingsPage.uninstallDesktopMacos"
                  : deploymentProfile === "android"
                  ? "settingsPage.uninstallDesktopAndroid"
                  : deploymentProfile === "linux-headless"
                  ? "settingsPage.uninstallHint"
                  : "settingsPage.uninstallDesktopLinux",
              )}
            </p>
            <div>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => setShowUninstall(true)}
              >
                <Icon name="delete_forever" size={16} /> {t("settingsPage.uninstallAction")}
              </button>
            </div>
            <div className="settings-danger-manual">
              {t(
                deploymentProfile === "windows"
                  ? "settingsPage.uninstallManualHintWindows"
                  : deploymentProfile === "macos"
                  ? "settingsPage.uninstallManualHintMacos"
                  : deploymentProfile === "android"
                  ? "settingsPage.uninstallManualHintAndroid"
                  : deploymentProfile === "linux-headless"
                  ? "settingsPage.uninstallManualHintHeadless"
                  : "settingsPage.uninstallManualHintLinux",
              )}
            </div>
          </div>
        </div>
      </section>

      {showUninstall && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-error-text)" }}>
              <Icon name="delete_forever" size={20} /> {t("settingsPage.uninstallButton")}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>{t("settingsPage.uninstallConfirmText")}</p>
            <ul className="settings-uninstall-list">
              <li>{t("settingsPage.uninstallItemServices")}</li>
              <li>{t("settingsPage.uninstallItemApp")}</li>
              <li>{t("settingsPage.uninstallItemData")}</li>
              <li>{t("settingsPage.uninstallItemKeepPackages")}</li>
            </ul>
            <label className="form-label" style={{ marginBottom: "4px" }}>
              {t("settingsPage.uninstallTypeLabel", { phrase: UNINSTALL_PHRASE })}
            </label>
            <input
              type="text"
              className="form-control"
              value={uninstallConfirm}
              onChange={(e) => setUninstallConfirm(e.target.value)}
              placeholder={UNINSTALL_PHRASE}
              autoFocus
            />
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => { setShowUninstall(false); setUninstallConfirm(""); }} disabled={uninstalling}>
                {t("common.cancel")}
              </button>
              <button type="button" className="btn btn-danger" onClick={handleUninstall} disabled={!uninstallReady || uninstalling}>
                {uninstalling ? t("settingsPage.uninstallInProgress") : t("settingsPage.uninstallConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      )}

      {showResetData && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-error-text)" }}>
              <Icon name="cleaning_services" size={20} /> {t("settingsPage.resetDataButton")}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t("settingsPage.resetDataConfirmText")}
            </p>
            <ul className="settings-uninstall-list">
              <li>{t("settingsPage.resetDataItemMedia")}</li>
              <li>{t("settingsPage.resetDataItemDb")}</li>
              <li>{t("settingsPage.resetDataItemKeepApp")}</li>
            </ul>
            <label className="form-label" style={{ marginBottom: "4px" }}>
              {t("settingsPage.resetDataTypeLabel", { phrase: RESET_DATA_PHRASE })}
            </label>
            <input
              type="text"
              className="form-control"
              value={resetDataConfirm}
              onChange={(e) => setResetDataConfirm(e.target.value)}
              placeholder={RESET_DATA_PHRASE}
              autoFocus
            />
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => { setShowResetData(false); setResetDataConfirm(""); }}
                disabled={resettingData}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleResetData}
                disabled={!resetDataReady || resettingData}
              >
                {resettingData ? t("settingsPage.resetDataInProgress") : t("settingsPage.resetDataConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
