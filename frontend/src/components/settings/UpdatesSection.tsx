"use client";
import { errorMessage } from "@/lib/apiError";
import React, { useEffect, useState } from "react";
import { channelI18nSuffix, channelLogoUrl, isRollingReleaseChannel, RELEASE_CHANNELS, type UpdateChannel } from "@/lib/releaseChannel";
import Icon from "@/components/Icon";
import ChannelConfirmDialog from "./ChannelConfirmDialog";
import ReleaseBanner from "./ReleaseBanner";
import StoreUpdatePanel from "./StoreUpdatePanel";
import TorUpdateSettings from "./TorUpdateSettings";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import type { SettingsData, UpdateInfo } from "./types";

interface UpdatesSectionProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  data: SettingsData;
  setData: React.Dispatch<React.SetStateAction<SettingsData | null>>;
  showToast: ShowToast;
  hidden: boolean;
  openSection: (sectionId: string) => void;
}

export default function UpdatesSection({ t, data, setData, showToast, hidden, openSection }: UpdatesSectionProps) {
  const [confirmingChannel, setConfirmingChannel] = useState<UpdateChannel | null>(null);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [storeBusy, setStoreBusy] = useState(false);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [applyingUpdate, setApplyingUpdate] = useState(false);
  const [changingChannel, setChangingChannel] = useState(false);

  const checkForUpdates = async (silent = false) => {
    setCheckingUpdate(true);
    try {
      const res = await fetch(getApiUrl(`/updates/check${silent ? "" : "?refresh=1"}`), { cache: "no-store" });
      if (res.ok) {
        const info: UpdateInfo = await res.json();
        setUpdateInfo(info);
        if (info.store_managed) {
          const state = info.store?.state;
          if (state === "available") {
            showToast(t("settingsPage.storeAvailable"), "warning", () => {
              openSection("updates-section");
            });
          } else if (!silent) {
            showToast(state === "none" ? t("settingsPage.storeUpToDate") : t("settingsPage.storeUnavailable"), state === "none" ? "success" : "warning");
          }
          return;
        }
        if (info.has_update && info.is_downgrade && silent) {
        } else if (info.has_update) {
          showToast(
            `${t("settingsPage.updateAvailable")} (${info.latest_version})`,
            "warning",
            () => {
              openSection("updates-section");
            },
          );
        } else if (!silent) {
          if (info.online) {
            showToast(t("settingsPage.upToDate"), "success");
          } else {
            showToast(info.message || t("settingsPage.updateError"), "warning");
          }
        }
      } else if (!silent) {
        showToast(t("settingsPage.updateError"), "error");
      }
    } catch {
      if (!silent) showToast(t("settingsPage.updateError"), "error");
    } finally {
      setCheckingUpdate(false);
    }
  };

  const handleStoreAction = async (action: "start" | "complete" | "open") => {
    setStoreBusy(true);
    try {
      const res = await fetch(getApiUrl(`/updates/store/${action}`), { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        showToast(errorMessage(body, t("settingsPage.storeActionError")), "error");
        return;
      }
      if (action === "start") showToast(t("settingsPage.storeStarted"), "success");
      if (action !== "open") await checkForUpdates(true);
    } catch {
      showToast(t("settingsPage.storeActionError"), "error");
    } finally {
      setStoreBusy(false);
    }
  };

  const storeDownloading = updateInfo?.store?.state === "downloading";
  useEffect(() => {
    if (!storeDownloading) return;
    const timer = setInterval(() => { void checkForUpdates(true); }, 5000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seule la présence d'un téléchargement en cours compte
  }, [storeDownloading]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- vérification ponctuelle contre une API externe (GitHub via le backend), pas un calcul dérivable au rendu
    checkForUpdates(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule vérification au montage, volontairement indépendante des re-rendus de checkForUpdates
  }, []);

  const handleApplyUpdate = async () => {
    const confirmText = updateInfo?.is_downgrade
      ? t("settingsPage.confirmDowngrade", { version: updateInfo.latest_version ?? "" })
      : t("settingsPage.applyUpdate") + " ?";
    if (!window.confirm(confirmText)) return;
    setApplyingUpdate(true);
    try {
      const res = await fetch(getApiUrl("/updates/apply"), { method: "POST" });
      if (res.ok) {
        showToast(t("settingsPage.updateInProgressHint"));
      } else if (res.status === 409) {
        showToast(t("settingsPage.updateAlreadyInProgress"), "warning");
      } else {
        const body = await res.json().catch(() => null);
        showToast(errorMessage(body, t("settingsPage.updateError")), "error");
      }
    } catch {
      showToast(t("settingsPage.updateError"), "error");
    } finally {
      setApplyingUpdate(false);
    }
  };

  const handleAutoUpdateChange = async (patch: {
    auto_update_enabled?: "true" | "false";
    auto_update_time?: string;
    update_tor?: "true" | "false";
    update_tor_proxy?: string;
  }) => {
    if (!data) return;
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (res.ok) {
        setData(await res.json());
        showToast(t("settingsPage.autoUpdateSaved"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(errorMessage(err, t("settingsPage.saveError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  const handleChannelChange = async (channel: UpdateChannel) => {
    if (!data || data.update_channel === channel || changingChannel) return;
    setChangingChannel(true);
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ update_channel: channel }),
      });
      if (res.ok) {
        setData(await res.json());
        showToast(t(isRollingReleaseChannel(channel) ? "settingsPage.updateChannelJoined" : "settingsPage.updateChannelLeft", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(channel)}`) }));
        checkForUpdates();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(errorMessage(err, t("settingsPage.saveError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setChangingChannel(false);
    }
  };

  return (
    <>
        <section className="live-block" id="updates-section" hidden={hidden}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
            <h3 style={{ margin: 0 }}>
              <Icon name="system_update" size={18} /> {t("settingsPage.updatesSection")}
            </h3>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ minHeight: "40px", padding: "6px 16px" }}
              onClick={() => checkForUpdates()}
              disabled={checkingUpdate || applyingUpdate}
            >
              <Icon
                name="sync"
                size={16}
                className={checkingUpdate ? "olc-spin" : ""}
              />
              {checkingUpdate ? t("settingsPage.checkingUpdates") : t("settingsPage.checkUpdates")}
            </button>
          </div>
          <p className="settings-hint" style={{ marginTop: "4px" }}>
            {t("settingsPage.updatesHint")}
          </p>
  
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "8px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>
                {t("settingsPage.currentVersion")} :
              </span>
              <span className="update-badge">
                <strong>{updateInfo?.current_version ?? "…"}</strong>
                {updateInfo?.current_commit && updateInfo.current_commit !== "unknown" && (
                  <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "0.75rem", opacity: 0.8 }}>
                    ({updateInfo.current_commit})
                  </span>
                )}
              </span>
              {updateInfo?.checked_at && (
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                  {t("settingsPage.lastChecked")} : {new Date(updateInfo.checked_at).toLocaleTimeString()}
                </span>
              )}
            </div>
  
            {!data.store_managed && (
              <>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
              <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
                {t("settingsPage.updateChannelLabel")}
              </span>
              <div
                style={{
                  display: "inline-flex",
                  borderRadius: "var(--radius-md)",
                  overflow: "hidden",
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-surface-elevated)",
                }}
              >
                {RELEASE_CHANNELS.map((channel) => (
                  <button
                    key={channel}
                    type="button"
                    className={`btn btn-sm ${data.update_channel === channel ? "btn-primary" : "btn-secondary"}`}
                    style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: "6px" }}
                    onClick={() => {
                      if (!isRollingReleaseChannel(channel)) handleChannelChange(channel);
                      else if (data.update_channel !== channel) setConfirmingChannel(channel);
                    }}
                    disabled={changingChannel}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={channelLogoUrl(channel)} alt="" width={18} height={18} style={{ borderRadius: "4px" }} />
                    {t(`settingsPage.updateChannel${channelI18nSuffix(channel)}`)}
                  </button>
                ))}
              </div>
            </div>
            <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.updateChannelHint")}</p>
            {data.update_tor_supported && (
              <TorUpdateSettings t={t} data={data} setData={setData} handleAutoUpdateChange={handleAutoUpdateChange} />
            )}
              </>
            )}
  
            {data.store_managed && (
              <StoreUpdatePanel t={t} updateInfo={updateInfo} storeBusy={storeBusy} handleStoreAction={handleStoreAction} />
            )}
            {!data.store_managed && data.auto_update_supported !== false && (
              <>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
              <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
                {t("settingsPage.autoUpdateSection")}
              </span>
              <label className="ra-switch" title={t("settingsPage.autoUpdateToggleLabel")}>
                <input
                  type="checkbox"
                  checked={data.auto_update_enabled === "true"}
                  onChange={(e) => handleAutoUpdateChange({ auto_update_enabled: e.target.checked ? "true" : "false" })}
                />
                <span className="ra-switch-track" />
              </label>
            </div>
            {data.auto_update_enabled === "true" && (
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <label htmlFor="auto-update-time" className="form-label" style={{ margin: 0 }}>
                  {t("settingsPage.autoUpdateTimeLabel")}
                </label>
                <input
                  id="auto-update-time"
                  type="time"
                  className="form-control"
                  style={{ maxWidth: "140px" }}
                  value={data.auto_update_time}
                  onChange={(e) => setData({ ...data, auto_update_time: e.target.value })}
                  onBlur={(e) => handleAutoUpdateChange({ auto_update_time: e.target.value })}
                />
              </div>
            )}
            <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.autoUpdateToggleHint")}</p>
              </>
            )}
  
            {updateInfo && !updateInfo.store_managed && (
              <ReleaseBanner t={t} updateInfo={updateInfo} applyingUpdate={applyingUpdate} handleApplyUpdate={handleApplyUpdate} />
            )}
          </div>
        </section>
  
        {confirmingChannel && (
          <ChannelConfirmDialog
            t={t}
            confirmingChannel={confirmingChannel}
            changingChannel={changingChannel}
            onCancel={() => setConfirmingChannel(null)}
            onConfirm={() => { const channel = confirmingChannel; setConfirmingChannel(null); handleChannelChange(channel); }}
          />
        )}
    </>
  );
}
