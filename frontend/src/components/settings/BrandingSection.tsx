"use client";
import React, { useState } from "react";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

export default function BrandingSection({ hidden, showToast }: { hidden: boolean; showToast: ShowToast }) {
  const { t, hasCustomLogo, activeLogo, setActiveLogo, refreshBranding } = useAppSettings();
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const handleLogoUpload = async (file: File) => {
    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(getApiUrl("/settings/logo"), { method: "POST", body: formData });
      if (res.ok) {
        refreshBranding();
        showToast(t("settingsPage.logoUploadSuccess"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(errorMessage(err, t("settingsPage.logoUploadError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleLogoReset = async () => {
    setUploadingLogo(true);
    try {
      const res = await fetch(getApiUrl("/settings/logo"), { method: "DELETE" });
      if (res.ok) {
        refreshBranding();
        showToast(t("settingsPage.logoResetSuccess"));
      } else {
        showToast(t("settingsPage.logoUploadError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setUploadingLogo(false);
    }
  };

  return (
      <section className="live-block" id="section-branding" hidden={hidden}>
        <h3><Icon name="image" size={18} /> {t("settingsPage.brandingSection")}</h3>
        <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "24px", flexWrap: "wrap" }}>
          <div
            style={{
              width: "180px",
              height: "84px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "var(--radius-md)",
              padding: "10px",
              flexShrink: 0,
              overflow: "hidden",
            }}
          >
            <AppLogo size={54} />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px", flexGrow: 1, minWidth: "260px" }}>
            {hasCustomLogo && (
              <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <span className="form-label" style={{ margin: 0, fontSize: "0.85rem" }}>
                  {t("settingsPage.activeLogoLabel")}
                </span>
                <div
                  style={{
                    display: "inline-flex",
                    borderRadius: "var(--radius-md)",
                    overflow: "hidden",
                    border: "1px solid var(--border-color)",
                    background: "var(--bg-surface-elevated)",
                  }}
                >
                  <button
                    type="button"
                    className={`btn btn-sm ${activeLogo === "default" ? "btn-primary" : "btn-secondary"}`}
                    style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px" }}
                    onClick={() => setActiveLogo("default")}
                  >
                    {t("settingsPage.logoBobine")}
                  </button>
                  <button
                    type="button"
                    className={`btn btn-sm ${activeLogo === "custom" ? "btn-primary" : "btn-secondary"}`}
                    style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px" }}
                    onClick={() => setActiveLogo("custom")}
                  >
                    {t("settingsPage.logoCustom")}
                  </button>
                </div>
              </div>
            )}

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
              <label className="btn btn-secondary" style={{ height: "38px", cursor: uploadingLogo ? "wait" : "pointer" }}>
                <Icon name="upload" size={16} /> {hasCustomLogo ? t("settingsPage.logoUploadReplace") : t("settingsPage.logoUploadLabel")}
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  style={{ display: "none" }}
                  disabled={uploadingLogo}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleLogoUpload(file);
                    e.target.value = "";
                  }}
                />
              </label>

              {hasCustomLogo && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ height: "38px", color: "var(--accent-error-text)" }}
                  onClick={() => {
                    if (window.confirm(t("settingsPage.logoDeleteConfirm"))) {
                      handleLogoReset();
                    }
                  }}
                  disabled={uploadingLogo}
                  title={t("settingsPage.logoDeleteButton")}
                >
                  <Icon name="delete" size={16} /> {t("settingsPage.logoDeleteButton")}
                </button>
              )}
            </div>

            <p className="settings-hint" style={{ margin: 0 }}>
              {t("settingsPage.logoHint")}
            </p>
          </div>
        </div>
      </section>
  );
}
