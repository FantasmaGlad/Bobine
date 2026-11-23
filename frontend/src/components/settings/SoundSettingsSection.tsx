"use client";

import { useEffect, useState } from "react";
import SoundSection from "@/components/devices/SoundSection";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { devicesRequest } from "@/lib/devices/request";
import type { DevicesStatus } from "@/lib/devices/types";
import { useRadioFeed } from "@/lib/useRadioFeed";
import type { ShowToast } from "@/lib/useToast";

export default function SoundSettingsSection({ hidden, showToast }: { hidden: boolean; showToast: ShowToast }) {
  const { t } = useAppSettings();
  const [status, setStatus] = useState<DevicesStatus | null>(null);
  useEffect(() => {
    if (hidden || status) return;
    void devicesRequest<DevicesStatus>("/status").then((result) => { if (result.ok) setStatus(result.data); });
  }, [hidden, status]);
  const feed = useRadioFeed(!hidden && !!status, !hidden && !!status);
  return (
    <section className="settings-stack" id="section-sound" hidden={hidden}>
      {status
        ? <SoundSection caps={status.capabilities ?? {}} local={status.local} refreshKey={0} notify={showToast} t={t} feed={feed} />
        : <p className="settings-hint">{t("devices.loading")}</p>}
    </section>
  );
}
