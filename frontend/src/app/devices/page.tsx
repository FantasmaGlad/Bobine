"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import { AccessGate, SecurityPanel } from "@/components/devices/AccessGate";
import AudioSection from "@/components/devices/AudioSection";
import BluetoothSection from "@/components/devices/BluetoothSection";
import WifiSection from "@/components/devices/WifiSection";
import type { Notify, SectionProps } from "@/components/devices/common";
import { devicesRequest, type DevicesStatus } from "@/lib/devicesApi";
import { useDevicesEvents } from "@/lib/useDevicesEvents";

// Périphériques : audio, Bluetooth et Wi-Fi de la machine qui diffuse. Fonction désactivée par défaut ;
// l'écran local est de confiance, tout autre appareil saisit un code PIN (voir docs/ARCHITECTURE.md).
// Même barre de sections horizontale que la bibliothèque radio.

type Tab = "audio" | "bluetooth" | "wifi" | "security";
const TAB_KEY = "bobine.devices.tab";

interface ToastState { message: string; type: "success" | "error" | "warning"; }

export default function DevicesPage() {
  const { t } = useAppSettings();
  const [status, setStatus] = useState<DevicesStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [tab, setTab] = useState<Tab>("audio");
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
      if (saved === "audio" || saved === "bluetooth" || saved === "wifi") setTab(saved);
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
  const section: SectionProps = { caps, local: status.local, refreshKey, notify, t };
  const tabButton = (id: Tab, icon: string, label: string) => (
    <button key={id} type="button" role="tab" aria-selected={tab === id} className={`display-output-btn olc-press ${tab === id ? "active" : ""}`} onClick={() => chooseTab(id)}>
      <Icon name={icon} size={16} /> {label}
    </button>
  );

  return (
    <div className="radio-lib radio-lib--tabs dv-page">
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}

      <div className="live-block channel-card rl-nav-card">
        <div className="channel-card-left">
          <h3><Icon name="devices" size={18} /> {t("devices.title")}</h3>
          {status.access === "granted" && (
            <span className="status-pill neutral" title={status.driver}>{t(`devices.platform.${status.platform}`)}</span>
          )}
        </div>
        {status.access === "granted" && (
          <div className="channel-card-right">
            <div className="display-output-switch rl-sections" role="tablist" aria-label={t("devices.sectionsLabel")}>
              <div className="display-output-buttons">
                {tabButton("audio", "speaker", t("devices.tabs.audio"))}
                {tabButton("bluetooth", "bluetooth", t("devices.tabs.bluetooth"))}
                {tabButton("wifi", "wifi", t("devices.tabs.wifi"))}
                {status.local && tabButton("security", "shield", t("devices.tabs.security"))}
              </div>
            </div>
            {!status.local && (
              <button type="button" className="btn btn-secondary" onClick={logout}><Icon name="logout" size={14} /> {t("devices.access.logout")}</button>
            )}
          </div>
        )}
      </div>

      <main className="radio-lib-main">
        {status.access !== "granted" ? (
          <>
            <AccessGate status={status} onChanged={onChanged} notify={notify} t={t} />
          </>
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
