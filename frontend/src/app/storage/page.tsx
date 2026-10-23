"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import { AccessGate } from "@/components/devices/AccessGate";
import type { Notify } from "@/components/devices/common";
import Explorer from "@/components/storage/Explorer";
import FormatAdvisor from "@/components/storage/FormatAdvisor";
import TransferStatus from "@/components/storage/TransferStatus";
import VolumeSheet from "@/components/storage/VolumeSheet";
import { PortableRow, VolumeRow } from "@/components/storage/VolumeRow";
import { storageErrorText } from "@/components/storage/common";
import { devicesRequest, type DevicesStatus } from "@/lib/devicesApi";
import { diffVolumes, encodeKey, storageRequest, type PortableListing, type StorageVolume, type VolumeListing } from "@/lib/storageApi";
import { useStorageEvents } from "@/lib/useStorageEvents";
import { usePointerGlow } from "@/lib/usePointerGlow";

// Stockage externe : supports amovibles et téléphones. Même accès que les périphériques (PIN, écran local de confiance).
// Une liste, UNE action principale par support (Explorer), puis Importer ou Utiliser comme extension ; le reste est dans « Options ».

interface ToastState { message: string; type: "success" | "error" | "warning"; }
interface OpenSource { key: string; name: string; portable: boolean; volume: StorageVolume | null; }

export default function StoragePage() {
  const { t, language } = useAppSettings();
  const lang = language === "en" ? "en" : "fr";
  const rootRef = useRef<HTMLDivElement>(null);
  usePointerGlow(rootRef);
  const [status, setStatus] = useState<DevicesStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [listing, setListing] = useState<VolumeListing | null>(null);
  const [portable, setPortable] = useState<PortableListing | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [opening, setOpening] = useState<string | null>(null);
  const [explorer, setExplorer] = useState<OpenSource | null>(null);
  const [sheetKey, setSheetKey] = useState<string | null>(null);
  const [advisor, setAdvisor] = useState(false);
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [modes, setModes] = useState<Record<string, "import" | "index" | "export">>({});
  const previous = useRef<StorageVolume[] | null>(null);

  const notify: Notify = useCallback((message, type = "success") => setToast({ message, type }), []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  const loadStatus = useCallback(async () => {
    const result = await devicesRequest<DevicesStatus>("/status");
    if (result.ok) {
      setStatus(result.data);
      setLoadError(false);
    } else setLoadError(true);
  }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial d'une ressource externe (API)
    void loadStatus();
  }, [loadStatus]);

  const granted = status?.access === "granted";

  const reload = useCallback(async () => {
    const [volumes, phones] = await Promise.all([storageRequest<VolumeListing>("/volumes"), storageRequest<PortableListing>("/portable")]);
    if (volumes.ok) {
      const before = previous.current;
      previous.current = volumes.data.volumes;
      setListing(volumes.data);
      if (before) {
        const abrupt = new Set(volumes.data.recent_removals.filter((r) => r.abrupt).map((r) => r.key));
        const diff = diffVolumes(before, volumes.data.volumes, abrupt);
        const removed = diff.removed[0];
        if (removed?.abrupt) notify(t("storage.abrupt", { name: removed.name }), "warning");
        else if (removed) notify(t("storage.unplugged", { name: removed.name }), "success");
        else if (diff.added[0]) notify(t("storage.plugged", { name: diff.added[0] }), "success");
      }
    } else if (volumes.error.code === "pin_required" || volumes.error.code === "devices_disabled" || volumes.error.code === "pin_not_set") {
      void loadStatus();
    } else {
      notify(storageErrorText(volumes.error, t, lang), "error");
    }
    if (phones.ok) setPortable(phones.data);
  }, [notify, t, lang, loadStatus]);

  useEffect(() => {
    if (!granted) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial d'une ressource externe (API)
    void reload();
  }, [granted, reload]);

  // Branchements et retraits arrivent en direct (WebSocket, sans aucune donnée) ; l'état est relu par REST derrière le PIN.
  useStorageEvents((event) => { if (event.scope !== "jobs") void reload(); }, granted);

  const onChanged = useCallback(() => { void loadStatus(); void reload(); }, [loadStatus, reload]);

  const logout = async () => {
    await devicesRequest("/session", { method: "DELETE" });
    onChanged();
  };

  const openVolume = async (volume: StorageVolume) => {
    setOpening(volume.key);
    const result = volume.mounted ? { ok: true as const } : await storageRequest(`/volumes/${encodeKey(volume.key)}/mount`, { body: { mode: "ro" } });
    setOpening(null);
    if (!result.ok) {
      notify(storageErrorText(result.error, t, lang), "error");
      void reload();
      return;
    }
    setExplorer({ key: volume.key, name: volume.name, portable: false, volume });
    if (!volume.mounted) void reload();
  };

  const openPortable = async (id: string, name: string) => {
    setOpening(id);
    const result = await storageRequest(`/portable/${encodeKey(id)}/mount`, { body: {} });
    setOpening(null);
    if (!result.ok) {
      notify(storageErrorText(result.error, t, lang), "error");
      void reload();
      return;
    }
    setExplorer({ key: id, name, portable: true, volume: null });
  };

  const onJob = useCallback((jobId: string, mode: "import" | "index") => {
    setJobIds((ids) => [...ids, jobId]);
    setModes((m) => ({ ...m, [jobId]: mode }));
  }, []);

  if (loadError && !status) return <div className="rl-center-note">{t("storage.errors.network")}</div>;
  if (!status) return <div className="rl-center-note">{t("storage.loading")}</div>;

  const volumes = listing?.volumes ?? [];
  const phones = portable?.devices ?? [];
  const current = explorer?.volume ? volumes.find((v) => v.key === explorer.key) ?? explorer.volume : null;
  const sheetVolume = volumes.find((v) => v.key === sheetKey) ?? null;
  const ctx = { t, lang: lang as "fr" | "en", notify };
  const showJobs = jobIds.length > 0;

  return (
    <div className="radio-lib radio-lib--tabs dv-page st-page" ref={rootRef}>
      {toast && <div className={`toast ${toast.type}`} role="status"><span>{toast.message}</span></div>}

      <main className="radio-lib-main">
        {!granted ? (
          <AccessGate status={status} onChanged={onChanged} notify={notify} t={t} />
        ) : explorer ? (
          <>
            <Explorer
              {...ctx}
              volumeKey={explorer.key}
              name={explorer.name}
              portable={explorer.portable}
              canExtend={!!current && current.uuid_known}
              registered={!!current?.library?.registered}
              onClose={() => setExplorer(null)}
              onJob={onJob}
              onLibraryChanged={() => void reload()}
            />
            {showJobs && <TransferStatus {...ctx} jobIds={jobIds} modes={modes} onDone={() => void reload()} />}
          </>
        ) : (
          <div className="dv-section">
            {showJobs && <TransferStatus {...ctx} jobIds={jobIds} modes={modes} onDone={() => void reload()} />}
            {volumes.length === 0 && phones.length === 0 ? (
              <div className="rl-empty-state">
                <Icon name="usb" size={40} style={{ opacity: 0.25, marginBottom: "8px" }} />
                <p style={{ margin: 0, fontWeight: 600 }}>{t("storage.empty")}</p>
              </div>
            ) : (
              <div className="dv-list">
                {volumes.map((volume) => (
                  <VolumeRow key={volume.key} {...ctx} volume={volume} busy={opening === volume.key} onExplore={() => openVolume(volume)} onMore={() => setSheetKey(volume.key)} />
                ))}
                {phones.map((device) => (
                  <PortableRow key={device.id} {...ctx} device={device} busy={opening === device.id} onOpen={() => openPortable(device.id, device.name)} />
                ))}
              </div>
            )}
            <div className="dv-quiet-actions">
              <button type="button" className="dv-link-btn" onClick={() => setAdvisor(true)}><Icon name="help" size={14} /> {t("storage.details.formatAdvice")}</button>
              <button type="button" className="dv-link-btn" onClick={() => void reload()}><Icon name="refresh" size={14} /> {t("storage.refresh")}</button>
              {!status.local && <button type="button" className="dv-link-btn" onClick={logout}><Icon name="logout" size={14} /> {t("devices.access.logout")}</button>}
            </div>
          </div>
        )}
      </main>

      <VolumeSheet {...ctx} volume={sheetVolume} onClose={() => setSheetKey(null)} onChanged={() => void reload()} onAdvice={() => setAdvisor(true)} />
      <FormatAdvisor {...ctx} open={advisor} onClose={() => setAdvisor(false)} />
    </div>
  );
}
