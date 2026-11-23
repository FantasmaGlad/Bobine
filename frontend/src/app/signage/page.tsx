"use client";

import SignagePlayer from "@/components/signage/SignagePlayer";
import { useSignageLoop } from "@/components/signage/useSignageLoop";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { DisplayChannel } from "@/lib/displayChannel";
import { DEFAULT_OUTPUT } from "@/lib/outputs";
import { useClientSnapshot } from "@/lib/useClientSnapshot";
import { getDisplayChannel, useDisplayOutputRedirect } from "@/lib/useDisplayOutputRedirect";
import { useDisplayOutputs } from "@/lib/useDisplayOutputs";

export default function SignagePage() {
  const { t } = useAppSettings();
  const channel = useClientSnapshot<DisplayChannel>(() => getDisplayChannel("signage"), DEFAULT_OUTPUT);
  const outputs = useDisplayOutputs();
  useDisplayOutputRedirect("signage", outputs.cable, outputs.network);
  const { entries } = useSignageLoop(channel);
  return <SignagePlayer entries={entries ?? []} emptyLabel={entries === null ? "" : t("signage.empty")} />;
}
