"use client";
import { errorMessage } from "@/lib/apiError";
import React, { useState } from "react";
import { channelI18nSuffix, isRollingReleaseChannel, type UpdateChannel } from "@/lib/releaseChannel";
import Icon from "@/components/Icon";
import ChannelConfirmDialog from "./ChannelConfirmDialog";
import AutoUpdateSettings from "./updates/AutoUpdateSettings";
import ChannelPicker from "./updates/ChannelPicker";
import { useUpdateCheck } from "./updates/useUpdateCheck";
import ReleaseBanner from "./ReleaseBanner";
import StoreUpdatePanel from "./StoreUpdatePanel";
import TorUpdateSettings from "./TorUpdateSettings";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";
import type { SettingsData } from "./types";

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
  const { updateInfo, storeBusy, checkingUpdate, checkForUpdates, handleStoreAction } = useUpdateCheck(t, showToast, openSection);
  const [applyingUpdate, setApplyingUpdate] = useState(false);
  const [changingChannel, setChangingChannel] = useState(false);

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
            <ChannelPicker
              t={t} current={data.update_channel} disabled={changingChannel}
              onPick={(channel) => {
                if (!isRollingReleaseChannel(channel)) handleChannelChange(channel);
                else if (data.update_channel !== channel) setConfirmingChannel(channel);
              }}
            />
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
              <AutoUpdateSettings t={t} data={data} setData={setData} onChange={handleAutoUpdateChange} />
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
