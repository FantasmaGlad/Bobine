"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import SegmentedTabs from "@/components/SegmentedTabs";
import { AccessGate, SecurityPanel } from "@/components/devices/AccessGate";
import AudioSection from "@/components/devices/AudioSection";
import BluetoothSection from "@/components/devices/BluetoothSection";
import WifiSection from "@/components/devices/WifiSection";
import MapSection from "@/components/devices/MapSection";
import type { Notify, SectionProps } from "@/components/devices/common";
import { devicesRequest, type DevicesStatus } from "@/lib/devicesApi";
import { useDevicesEvents } from "@/lib/useDevicesEvents";
import { usePointerGlow } from "@/lib/usePointerGlow";

// Périphériques : audio, Bluetooth et Wi-Fi de la machine qui diffuse. Fonction désactivée par défaut ;
// l'écran local est de confiance, tout autre appareil saisit un code PIN (voir docs/ARCHITECTURE.md).
// Même barre de sections horizontale que la bibliothèque radio.

type Tab = "map" | "audio" | "bluetooth" | "wifi" | "security";
const TAB_KEY = "bobine.devices.tab";

interface ToastState { message: string; type: "success" | "error" | "warning"; }

export default function DevicesPage() {
  const { t } = useAppSettings();
  const rootRef = useRef<HTMLDivElement>(null);
  usePointerGlow(rootRef);
  const [status, setStatus] = useState<DevicesStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [tab, setTab] = useState<Tab>("map");
  const [focus, setFocus] = useState<{ id: string | null; nonce: number }>({ id: null, nonce: 0 });
  const [refreshKey, setRefreshKey] = useState(0);
  const [toast, setToast] = useState<ToastState | null>(null);

  const notify: Notify = useCallback((message, type = "success") => setToast({ message, type }), []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(TAB_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- restaure la dernière section (stockage local du navigateur)
      if (saved === "map" || saved === "audio" || saved === "bluetooth" || saved === "wifi") setTab(saved);
    } catch { /* stockage indisponible */ }
  }, []);
  const chooseTab = (next: Tab) => {
    setTab(next);
    try { if (next !== "security") window.localStorage.setItem(TAB_KEY, next); } catch { /* ignoré */ }
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
  useDevicesEvents(() => setRefreshKey((k) => k + 1), status?.access === "granted");

  const onChanged = useCallback(() => {
    setRefreshKey((k) => k + 1);
    void loadStatus();
  }, [loadStatus]);

  const logout = async () => {
    await devicesRequest("/session", { method: "DELETE" });
    onChanged();
  };

  if (loadError && !status) return <div className="rl-center-note">{t("devices.errors.network")}</div>;
  if (!status) return <div className="rl-center-note">{t("devices.loading")}</div>;

  const caps = status.capabilities ?? {};
  const section: SectionProps = { caps, local: status.local, refreshKey, notify, t, focusId: focus.id, focusNonce: focus.nonce };
  return (
    <div className="radio-lib radio-lib--tabs dv-page" ref={rootRef}>
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}

      {status.access === "granted" && (
        <div className="live-block channel-card rl-nav-card">
          {tab !== "security" && (
        <div className="channel-card-left">
              <h3><Icon name="devices" size={18} /> {t("devices.title")}</h3>
              {status.access === "granted" && (
                <span className="status-pill neutral" title={status.driver}>{t(`devices.platform.${status.platform}`)}</span>
              )}
            </div>
        )}
          {status.access === "granted" && (
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
                  ...(status.local ? [{ id: "security", icon: "shield", label: t("devices.tabs.security") }] : []),
                ]}
              />
              {!status.local && (
                <button type="button" className="btn btn-secondary" onClick={logout}><Icon name="logout" size={14} /> {t("devices.access.logout")}</button>
              )}
            </div>
          )}
        </div>
      )}

      <main className="radio-lib-main">
        {status.access !== "granted" ? (
          <AccessGate status={status} onChanged={onChanged} notify={notify} t={t} />
        ) : tab === "map" ? (
          <MapSection refreshKey={refreshKey} t={t} onOpen={(next, ref) => { chooseTab(next); setFocus((f) => ({ id: ref, nonce: f.nonce + 1 })); }} />
        ) : tab === "audio" ? (
          <AudioSection {...section} />
        ) : tab === "bluetooth" ? (
          <BluetoothSection {...section} />
        ) : tab === "wifi" ? (
          <WifiSection {...section} />
        ) : (
          <SecurityPanel status={status} onChanged={onChanged} notify={notify} t={t} />
        )}
      </main>
    </div>
  );
}
