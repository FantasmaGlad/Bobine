"use client";

import SignagePlayer from "@/components/signage/SignagePlayer";
import { useSignageLoop } from "@/components/signage/useSignageLoop";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { parseChannelParam, type DisplayChannel } from "@/lib/displayChannel";
import { useClientSnapshot } from "@/lib/useClientSnapshot";

export default function SignagePage() {
  const { t } = useAppSettings();
  const channel = useClientSnapshot<DisplayChannel>(() => parseChannelParam(window.location.search) ?? "cable", "cable");
  const { entries } = useSignageLoop(channel);
  return <SignagePlayer entries={entries ?? []} emptyLabel={entries === null ? "" : t("signage.empty")} />;
}
