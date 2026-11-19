"use client";

import { useState } from "react";
import { errorMessage } from "@/lib/apiError";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";

type ToastType = "success" | "error" | "warning";
type ShowToast = (message: string, type?: ToastType) => void;

export const normalizePhrase = (s: string) => s.trim().toUpperCase().replace(/É/g, "E");

function postConfirm(path: string, confirm: string) {
  return fetch(getApiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm }),
  });
}

export function useUninstall(showToast: ShowToast) {
  const { t } = useAppSettings();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      const res = await postConfirm("/settings/system/uninstall", confirm);
      const payload = await res.json().catch(() => ({}));
      if (res.ok) {
        showToast(payload.message || t("settingsPage.uninstallStarted"), "warning");
      } else {
        showToast(errorMessage(payload, t("settingsPage.uninstallError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setBusy(false);
      setOpen(false);
      setConfirm("");
    }
  };

  const cancel = () => { setOpen(false); setConfirm(""); };
  const ready = normalizePhrase(confirm) === "DESINSTALLER";
  return { open, setOpen, confirm, setConfirm, busy, run, cancel, ready };
}

export function useResetData(showToast: ShowToast) {
  const { t } = useAppSettings();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const ready = normalizePhrase(confirm) === "REINITIALISER";

  const run = async () => {
    if (!ready) return;
    setBusy(true);
    try {
      const res = await postConfirm("/settings/system/reset-data", confirm);
      if (res.ok) {
        showToast(t("settingsPage.resetDataSuccess"), "success");
        setOpen(false);
        setConfirm("");
      } else {
        const err = await res.json().catch(() => null);
        showToast(errorMessage(err, t("settingsPage.resetDataError")), "error");
      }
    } catch {
      showToast(t("settingsPage.resetDataError"), "error");
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => { setOpen(false); setConfirm(""); };
  return { open, setOpen, confirm, setConfirm, busy, run, cancel, ready };
}
