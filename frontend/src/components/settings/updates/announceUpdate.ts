import type { ShowToast } from "@/lib/useToast";
import type { UpdateInfo } from "../types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export function announceUpdate(info: UpdateInfo, silent: boolean, t: Translate, showToast: ShowToast, openUpdates: () => void) {
  if (info.store_managed) {
    const state = info.store?.state;
    if (state === "available") showToast(t("settingsPage.storeAvailable"), "warning", openUpdates);
    else if (!silent) showToast(state === "none" ? t("settingsPage.storeUpToDate") : t("settingsPage.storeUnavailable"), state === "none" ? "success" : "warning");
    return;
  }
  if (info.has_update && info.is_downgrade && silent) return;
  if (info.has_update) showToast(`${t("settingsPage.updateAvailable")} (${info.latest_version})`, "warning", openUpdates);
  else if (!silent) showToast(info.online ? t("settingsPage.upToDate") : info.message || t("settingsPage.updateError"), info.online ? "success" : "warning");
}
