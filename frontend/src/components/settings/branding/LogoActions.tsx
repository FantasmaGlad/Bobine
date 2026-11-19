"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";

export default function LogoActions({ uploadingLogo, handleLogoUpload, handleLogoReset }: {
  uploadingLogo: boolean;
  handleLogoUpload: (file: File) => void;
  handleLogoReset: () => void;
}) {
  const { t, hasCustomLogo } = useAppSettings();
  return (
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
  );
}
