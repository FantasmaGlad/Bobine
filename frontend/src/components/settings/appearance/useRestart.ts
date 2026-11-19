"use client";

import { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";

export function useRestart() {
  const { t } = useAppSettings();
  const [restarting, setRestarting] = useState(false);
  const [restartMessage, setRestartMessage] = useState<string | null>(null);
  const restartNow = async () => {
    setRestarting(true);
    setRestartMessage(null);
    try {
      const res = await fetch(getApiUrl("/settings/system/restart"), { method: "POST" });
      setRestartMessage(t(res.ok ? "settingsPage.languageRestarting" : "settingsPage.languageRestartFailed"));
      if (!res.ok) setRestarting(false);
      else {
        window.setTimeout(() => {
          setRestarting(false);
          setRestartMessage(t("settingsPage.languageRestartFailed"));
        }, 30000);
      }
    } catch {
      setRestartMessage(t("settingsPage.languageRestartFailed"));
      setRestarting(false);
    }
  };

  return { restarting, restartMessage, restartNow };
}
