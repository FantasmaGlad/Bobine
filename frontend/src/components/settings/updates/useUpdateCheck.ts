import { useEffect, useState } from "react";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import type { UpdateInfo } from "../types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export function useUpdateCheck(t: Translate, showToast: ShowToast, openSection: (sectionId: string) => void) {
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [storeBusy, setStoreBusy] = useState(false);
  const [checkingUpdate, setCheckingUpdate] = useState(false);

  const checkForUpdates = async (silent = false) => {
    setCheckingUpdate(true);
    try {
      const res = await fetch(getApiUrl(`/updates/check${silent ? "" : "?refresh=1"}`), { cache: "no-store" });
      if (res.ok) {
        const info: UpdateInfo = await res.json();
        setUpdateInfo(info);
        if (info.store_managed) {
          const state = info.store?.state;
          if (state === "available") {
            showToast(t("settingsPage.storeAvailable"), "warning", () => {
              openSection("updates-section");
            });
          } else if (!silent) {
            showToast(state === "none" ? t("settingsPage.storeUpToDate") : t("settingsPage.storeUnavailable"), state === "none" ? "success" : "warning");
          }
          return;
        }
        if (info.has_update && info.is_downgrade && silent) {
        } else if (info.has_update) {
          showToast(
            `${t("settingsPage.updateAvailable")} (${info.latest_version})`,
            "warning",
            () => {
              openSection("updates-section");
            },
          );
        } else if (!silent) {
          if (info.online) {
            showToast(t("settingsPage.upToDate"), "success");
          } else {
            showToast(info.message || t("settingsPage.updateError"), "warning");
          }
        }
      } else if (!silent) {
        showToast(t("settingsPage.updateError"), "error");
      }
    } catch {
      if (!silent) showToast(t("settingsPage.updateError"), "error");
    } finally {
      setCheckingUpdate(false);
    }
  };

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

  const storeDownloading = updateInfo?.store?.state === "downloading";
  useEffect(() => {
    if (!storeDownloading) return;
    const timer = setInterval(() => { void checkForUpdates(true); }, 5000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seule la présence d'un téléchargement en cours compte
  }, [storeDownloading]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- vérification ponctuelle contre une API externe (GitHub via le backend), pas un calcul dérivable au rendu
    checkForUpdates(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule vérification au montage, volontairement indépendante des re-rendus de checkForUpdates
  }, []);

  return { updateInfo, storeBusy, checkingUpdate, checkForUpdates, handleStoreAction };
}
