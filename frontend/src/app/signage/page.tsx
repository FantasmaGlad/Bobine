"use client";

import SignagePlayer from "@/components/signage/SignagePlayer";
import { useSignageLoop } from "@/components/signage/useSignageLoop";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { DisplayChannel } from "@/lib/displayChannel";
import { useClientSnapshot } from "@/lib/useClientSnapshot";
import { getDisplayChannel, useDisplayOutputRedirect } from "@/lib/useDisplayOutputRedirect";
import { useDisplayOutputs } from "@/lib/useDisplayOutputs";

export default function SignagePage() {
  const { t } = useAppSettings();
  const channel = useClientSnapshot<DisplayChannel>(() => getDisplayChannel("signage"), "cable");
  const outputs = useDisplayOutputs();
  useDisplayOutputRedirect("signage", outputs.cable, outputs.network);
  const { entries } = useSignageLoop(channel);
  return <SignagePlayer entries={entries ?? []} emptyLabel={entries === null ? "" : t("signage.empty")} />;
}
