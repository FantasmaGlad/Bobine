"use client";
import React, { useState } from "react";
import { isRollingReleaseChannel, type UpdateChannel } from "@/lib/releaseChannel";
import Icon from "@/components/Icon";
import ChannelConfirmDialog from "./ChannelConfirmDialog";
import AutoUpdateSettings from "./updates/AutoUpdateSettings";
import ChannelPicker from "./updates/ChannelPicker";
import CurrentVersionRow from "./updates/CurrentVersionRow";
import { useUpdateCheck } from "./updates/useUpdateCheck";
import { useApplyUpdate, useSettingsUpdates } from "./updates/useUpdateActions";
import ReleaseBanner from "./ReleaseBanner";
import StoreUpdatePanel from "./StoreUpdatePanel";
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
  const { applyingUpdate, handleApplyUpdate } = useApplyUpdate(t, showToast, updateInfo?.is_downgrade, updateInfo?.latest_version);
  const { changingChannel, handleAutoUpdateChange, handleChannelChange } = useSettingsUpdates(t, data, setData, showToast, checkForUpdates);

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
              <Icon name="sync" size={16} className={checkingUpdate ? "olc-spin" : ""} />
              {checkingUpdate ? t("settingsPage.checkingUpdates") : t("settingsPage.checkUpdates")}
            </button>
          </div>
          <p className="settings-hint" style={{ marginTop: "4px" }}>
            {t("settingsPage.updatesHint")}
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "8px" }}>
            <CurrentVersionRow t={t} updateInfo={updateInfo} />
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
