import { useEffect, useEffectEvent, useState } from "react";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import type { UpdateInfo } from "../types";
import { announceUpdate } from "./announceUpdate";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export function useUpdateCheck(t: Translate, showToast: ShowToast, openSection: (sectionId: string) => void) {
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [checkingUpdate, setCheckingUpdate] = useState(true);

  const fetchUpdateInfo = (silent: boolean) => fetch(getApiUrl(`/updates/check${silent ? "" : "?refresh=1"}`), { cache: "no-store" })
    .then(async (res) => {
      if (!res.ok) {
        if (!silent) showToast(t("settingsPage.updateError"), "error");
        return;
      }
      const info: UpdateInfo = await res.json();
      setUpdateInfo(info);
      announceUpdate(info, silent, t, showToast, () => openSection("updates-section"));
    })
    .catch(() => {
      if (!silent) showToast(t("settingsPage.updateError"), "error");
    })
    .finally(() => setCheckingUpdate(false));

  const checkForUpdates = (silent = false) => {
    setCheckingUpdate(true);
    return fetchUpdateInfo(silent);
  };

  const { storeBusy, handleStoreAction } = useStoreAction(t, showToast, checkForUpdates);

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

function useStoreAction(t: Translate, showToast: ShowToast, checkForUpdates: (silent?: boolean) => Promise<void>) {
  const [storeBusy, setStoreBusy] = useState(false);
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

  return { storeBusy, handleStoreAction };
}
