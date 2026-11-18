import { useEffect, useEffectEvent, useState } from "react";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import type { UpdateInfo } from "../types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export function useUpdateCheck(t: Translate, showToast: ShowToast, openSection: (sectionId: string) => void) {
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [storeBusy, setStoreBusy] = useState(false);
  const [checkingUpdate, setCheckingUpdate] = useState(true);

  const announce = (info: UpdateInfo, silent: boolean) => {
    const openUpdates = () => openSection("updates-section");
    if (info.store_managed) {
      const state = info.store?.state;
      if (state === "available") showToast(t("settingsPage.storeAvailable"), "warning", openUpdates);
      else if (!silent) showToast(state === "none" ? t("settingsPage.storeUpToDate") : t("settingsPage.storeUnavailable"), state === "none" ? "success" : "warning");
      return;
    }
    if (info.has_update && info.is_downgrade && silent) return;
    if (info.has_update) showToast(`${t("settingsPage.updateAvailable")} (${info.latest_version})`, "warning", openUpdates);
    else if (!silent) showToast(info.online ? t("settingsPage.upToDate") : info.message || t("settingsPage.updateError"), info.online ? "success" : "warning");
  };

  const fetchUpdateInfo = (silent: boolean) => fetch(getApiUrl(`/updates/check${silent ? "" : "?refresh=1"}`), { cache: "no-store" })
    .then(async (res) => {
      if (!res.ok) {
        if (!silent) showToast(t("settingsPage.updateError"), "error");
        return;
      }
      const info: UpdateInfo = await res.json();
      setUpdateInfo(info);
      announce(info, silent);
    })
    .catch(() => {
      if (!silent) showToast(t("settingsPage.updateError"), "error");
    })
    .finally(() => setCheckingUpdate(false));

  const handleStoreAction = async (action: "start" | "complete" | "open") => {
    setStoreBusy(true);
    try {
      const res = await fetch(getApiUrl(`/updates/store/${action}`), { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        showToast(errorMessage(body, t("settingsPage.storeActionError")), "error");
        return;
      }
      if (action === "start") showToast(t("settingsPage.storeStarted"), "success");
      if (action !== "open") await checkForUpdates(true);
    } catch {
      showToast(t("settingsPage.storeActionError"), "error");
    } finally {
      setStoreBusy(false);
    }
  };

  const checkForUpdates = (silent = false) => {
    setCheckingUpdate(true);
    return fetchUpdateInfo(silent);
  };

  const refreshSilently = useEffectEvent(() => fetchUpdateInfo(true));

  const storeDownloading = updateInfo?.store?.state === "downloading";
  useEffect(() => {
    if (!storeDownloading) return;
    const timer = setInterval(refreshSilently, 5000);
    return () => clearInterval(timer);
  }, [storeDownloading]);

  useEffect(() => {
    void refreshSilently();
  }, []);

  return { updateInfo, storeBusy, checkingUpdate, checkForUpdates, handleStoreAction };
}
