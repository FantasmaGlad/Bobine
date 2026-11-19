"use client";

import { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

export function useLogo(showToast: ShowToast) {
  const { t, refreshBranding } = useAppSettings();
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

  return { uploadingLogo, handleLogoUpload, handleLogoReset };
}
