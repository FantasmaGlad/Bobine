"use client";

import React, { useState } from "react";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import { channelI18nSuffix, isRollingReleaseChannel, type UpdateChannel } from "@/lib/releaseChannel";
import type { ShowToast } from "@/lib/useToast";
import type { SettingsData } from "../types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export type AutoUpdatePatch = {
  auto_update_enabled?: "true" | "false";
  auto_update_time?: string;
};

function putSettings(body: object) {
  return fetch(getApiUrl("/settings"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function useApplyUpdate(t: Translate, showToast: ShowToast, isDowngrade: boolean | undefined, latest: string | null | undefined) {
  const [applyingUpdate, setApplyingUpdate] = useState(false);
  const handleApplyUpdate = async () => {
    const confirmText = isDowngrade
      ? t("settingsPage.confirmDowngrade", { version: latest ?? "" })
      : t("settingsPage.applyUpdate") + " ?";
    if (!window.confirm(confirmText)) return;
    setApplyingUpdate(true);
    try {
      const res = await fetch(getApiUrl("/updates/apply"), { method: "POST" });
      if (res.ok) {
        showToast(t("settingsPage.updateInProgressHint"));
      } else if (res.status === 409) {
        showToast(t("settingsPage.updateAlreadyInProgress"), "warning");
      } else {
        const body = await res.json().catch(() => null);
        showToast(errorMessage(body, t("settingsPage.updateError")), "error");
      }
    } catch {
      showToast(t("settingsPage.updateError"), "error");
    } finally {
      setApplyingUpdate(false);
    }
  };
  return { applyingUpdate, handleApplyUpdate };
}

export function useSettingsUpdates(
  t: Translate,
  data: SettingsData,
  setData: React.Dispatch<React.SetStateAction<SettingsData | null>>,
  showToast: ShowToast,
  checkForUpdates: () => void,
) {
  const [changingChannel, setChangingChannel] = useState(false);

  const handleAutoUpdateChange = async (patch: AutoUpdatePatch) => {
    if (!data) return;
    try {
      const res = await putSettings(patch);
      if (res.ok) {
        setData(await res.json());
        showToast(t("settingsPage.autoUpdateSaved"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(errorMessage(err, t("settingsPage.saveError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  const handleChannelChange = async (channel: UpdateChannel) => {
    if (!data || data.update_channel === channel || changingChannel) return;
    setChangingChannel(true);
    try {
      const res = await putSettings({ update_channel: channel });
      if (res.ok) {
        setData(await res.json());
        showToast(t(isRollingReleaseChannel(channel) ? "settingsPage.updateChannelJoined" : "settingsPage.updateChannelLeft", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(channel)}`) }));
        checkForUpdates();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(errorMessage(err, t("settingsPage.saveError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setChangingChannel(false);
    }
  };

  return { changingChannel, handleAutoUpdateChange, handleChannelChange };
}
