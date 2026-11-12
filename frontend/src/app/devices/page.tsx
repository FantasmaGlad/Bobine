"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import SegmentedTabs from "@/components/SegmentedTabs";
import AudioSection from "@/components/devices/AudioSection";
import BluetoothSection from "@/components/devices/BluetoothSection";
import WifiSection from "@/components/devices/WifiSection";
import MapSection from "@/components/devices/MapSection";
import MixerSection from "@/components/devices/MixerSection";
import VideoSoundSection from "@/components/devices/VideoSoundSection";
import RoutingSection from "@/components/devices/RoutingSection";
import type { SectionProps } from "@/components/devices/common";
import { devicesRequest, type DevicesStatus } from "@/lib/devicesApi";
import { useDevicesEvents } from "@/lib/useDevicesEvents";
import { useRadioFeed } from "@/lib/useRadioFeed";
import { useToast } from "@/lib/useToast";

// Périphériques : audio, Bluetooth et Wi-Fi de la machine qui diffuse. Tout appareil du réseau local de confiance
// y accède directement (voir docs/ARCHITECTURE.md).
// Même barre de sections horizontale que la bibliothèque radio.

type Tab = "map" | "audio" | "bluetooth" | "wifi" | "routing" | "mixer" | "videosound";
const TAB_KEY = "bobine.devices.tab";

export default function DevicesPage() {
  const { t } = useAppSettings();
  const [status, setStatus] = useState<DevicesStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [tab, setTab] = useState<Tab>("map");
  const [focus, setFocus] = useState<{ id: string | null; nonce: number }>({ id: null, nonce: 0 });
  const [refreshKey, setRefreshKey] = useState(0);
  const { toast, showToast: notify } = useToast();

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(TAB_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- restaure la dernière section (stockage local du navigateur)
      if (saved === "map" || saved === "audio" || saved === "bluetooth" || saved === "wifi" || saved === "routing" || saved === "mixer" || saved === "videosound") setTab(saved);
    } catch { /* stockage indisponible */ }
  }, []);
  const chooseTab = (next: Tab) => {
    setTab(next);
    try { window.localStorage.setItem(TAB_KEY, next); } catch { /* ignoré */ }
  };

  const loadStatus = useCallback(async () => {
    const result = await devicesRequest<DevicesStatus>("/status");
    if (result.ok) {
      setStatus(result.data);
      setLoadError(false);
    } else {
      setLoadError(true);
    }
  }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial d'une ressource externe (API)
    void loadStatus();
  }, [loadStatus]);

  // Évènements temps réel : relit les sections affichées (les évènements ne portent aucune donnée).
  useDevicesEvents(() => setRefreshKey((k) => k + 1), !!status);

  // Flux temps réel des sorties radio : seulement pour le graphe et la table de mixage ; le vumètre (mesure par le lecteur)
  // uniquement quand la table de mixage est affichée.
  const radioFeed = useRadioFeed(!!status && (tab === "routing" || tab === "mixer"), !!status && tab === "mixer");

  if (loadError && !status) return <div className="rl-center-note">{t("devices.errors.network")}</div>;
  if (!status) return <div className="rl-center-note">{t("devices.loading")}</div>;

  const caps = status.capabilities ?? {};
  const section: SectionProps = { caps, local: status.local, refreshKey, notify, t, focusId: focus.id, focusNonce: focus.nonce };
  return (
    <div className="radio-lib radio-lib--tabs dv-page">
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}

      <div className="live-block channel-card rl-nav-card rl-nav-card--centered">
        <div className="channel-card-right">
          <SegmentedTabs
            ariaLabel={t("devices.sectionsLabel")}
            value={tab}
            onChange={(id) => chooseTab(id as Tab)}
            tabs={[
              { id: "map", icon: "hub", label: t("devices.tabs.map") },
              { id: "audio", icon: "speaker", label: t("devices.tabs.audio") },
              { id: "bluetooth", icon: "bluetooth", label: t("devices.tabs.bluetooth") },
              { id: "wifi", icon: "wifi", label: t("devices.tabs.wifi") },
              { id: "routing", icon: "alt_route", label: t("devices.tabs.routing") },
              { id: "mixer", icon: "instant_mix", label: t("devices.tabs.mixer") },
              { id: "videosound", icon: "graphic_eq", label: t("devices.tabs.videosound") },
            ]}
          />
        </div>
      </div>

      <main className="radio-lib-main">
        {tab === "map" ? (
          <MapSection refreshKey={refreshKey} t={t} onOpen={(next, ref) => { chooseTab(next); setFocus((f) => ({ id: ref, nonce: f.nonce + 1 })); }} />
        ) : tab === "audio" ? (
          <AudioSection {...section} />
        ) : tab === "bluetooth" ? (
          <BluetoothSection {...section} />
        ) : tab === "wifi" ? (
          <WifiSection {...section} />
        ) : tab === "routing" ? (
          <RoutingSection {...section} feed={radioFeed} />
        ) : tab === "videosound" ? (
          <VideoSoundSection {...section} />
        ) : (
          <MixerSection {...section} feed={radioFeed} />
        )}
      </main>
    </div>
  );
}
