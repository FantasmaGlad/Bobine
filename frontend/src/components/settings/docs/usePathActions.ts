"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import { copyText } from "@/lib/clipboard";
import type { ShowToast } from "@/lib/useToast";

export function usePathActions(showToast: ShowToast) {
  const { t } = useAppSettings();
  const handleCopyPath = async (p: string) => {
    if (await copyText(p)) {
      showToast(t("settingsPage.paths.pathCopied"));
    } else {
      showToast(p);
    }
  };

  const handleOpenPath = async (p: string) => {
    try {
      const res = await fetch(getApiUrl("/settings/open-path"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: p }),
      });
      const resData = await res.json().catch(() => ({}));
      if (res.ok) {
        if (resData.status === "android") {
          await copyText(p);
          showToast(resData.message || t("settingsPage.paths.pathCopied"));
        } else {
          showToast(t("settingsPage.paths.folderOpened"));
        }
      } else {
        showToast(errorMessage(resData, t("settingsPage.openFolderError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  return { handleCopyPath, handleOpenPath };
}
