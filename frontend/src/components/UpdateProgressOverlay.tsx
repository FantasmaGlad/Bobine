"use client";

import { useAppSettings } from "@/lib/AppSettingsContext";
import { isHidden } from "./update-progress/updateStatus";
import UpdateToast from "./update-progress/UpdateToast";
import { useUpdateStatus } from "./update-progress/useUpdateStatus";

export default function UpdateProgressOverlay() {
  const { t } = useAppSettings();
  const { status, acknowledge } = useUpdateStatus();
  if (!status || isHidden(status)) return null;
  return <UpdateToast status={status} t={t} onDismiss={acknowledge} />;
}
