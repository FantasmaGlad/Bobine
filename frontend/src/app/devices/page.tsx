"use client";

import React, { useCallback, useEffect, useState } from "react";
import DevicesSection from "@/components/devices/DevicesSection";
import type { SectionProps } from "@/components/devices/shared/section";
import SoundSection from "@/components/devices/SoundSection";
import PageNav from "@/components/PageNav";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { devicesRequest } from "@/lib/devices/request";
import { type DevicesStatus } from "@/lib/devices/types";
import { oneOf } from "@/lib/urlView";
import { useRadioFeed } from "@/lib/useRadioFeed";
import { useServerEvent } from "@/lib/useServerEvent";
import { useToast } from "@/lib/useToast";
import { useUrlView } from "@/lib/useUrlView";

const VIEWS = oneOf(["devices", "sound"] as const, "devices");

export default function DevicesPage() {
  const { t } = useAppSettings();
  const [status, setStatus] = useState<DevicesStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [view, setView] = useUrlView("vue", VIEWS);
  const [refreshKey, setRefreshKey] = useState(0);
  const { toast, showToast: notify } = useToast();

  const loadStatus = useCallback(() => devicesRequest<DevicesStatus>("/status").then((result) => {
    if (result.ok) {
      setStatus(result.data);
      setLoadError(false);
    } else {
      setLoadError(true);
    }
  }), []);
  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const refreshDevices = useCallback(() => setRefreshKey((k) => k + 1), []);
  useServerEvent("devices_changed", refreshDevices, !!status);
  const radioFeed = useRadioFeed(!!status && view === "sound", !!status && view === "sound");

  if (loadError && !status) return <div className="rl-center-note">{t("devices.errors.network")}</div>;
  if (!status) return <div className="rl-center-note">{t("devices.loading")}</div>;

  const section: SectionProps = { caps: status.capabilities ?? {}, local: status.local, refreshKey, notify, t };
  return (
    <div className="radio-lib radio-lib--tabs dv-page">
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
      <PageNav
        tabs={[{ id: "devices", icon: "devices", label: t("devices.tabs.devices") }, { id: "sound", icon: "graphic_eq", label: t("devices.tabs.sound") }]}
        value={view}
        onChange={(id) => setView(VIEWS(id))}
        ariaLabel={t("devices.sectionsLabel")}
      />
      <main className="radio-lib-main">
        {view === "devices" ? <DevicesSection {...section} /> : <SoundSection {...section} feed={radioFeed} />}
      </main>
    </div>
  );
}
