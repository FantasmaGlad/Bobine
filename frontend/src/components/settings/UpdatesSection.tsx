"use client";
import { errorMessage } from "@/lib/apiError";
import React, { useEffect, useState } from "react";
import { channelI18nSuffix, channelLogoUrl, isRollingReleaseChannel, RELEASE_CHANNELS, type UpdateChannel } from "@/lib/releaseChannel";
import { formatBinarySize } from "@/lib/format";
import Icon from "@/components/Icon";
import MarkdownView from "@/components/MarkdownView";
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
  const [showReleaseNotes, setShowReleaseNotes] = useState(false);
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

  const [torCheck, setTorCheck] = useState<{ ok: boolean; source?: string; error?: string } | null>(null);
  const [torChecking, setTorChecking] = useState(false);
  const handleTorCheck = async () => {
    if (!data) return;
    setTorChecking(true);
    setTorCheck(null);
    try {
      const res = await fetch(getApiUrl("/updates/tor-check"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proxy: data.update_tor_proxy }),
      });
      const body = await res.json().catch(() => ({}));
      setTorCheck(res.ok ? body : { ok: false, error: errorMessage(body, t("settingsPage.saveError"))});
    } catch {
      setTorCheck({ ok: false, error: t("common.networkError") });
    } finally {
      setTorChecking(false);
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
              <>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
                  <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
                    {t("settingsPage.updateTorLabel")}
                  </span>
                  <label className="ra-switch" title={t("settingsPage.updateTorLabel")}>
                    <input
                      type="checkbox"
                      checked={data.update_tor === "true"}
                      onChange={(e) => handleAutoUpdateChange({ update_tor: e.target.checked ? "true" : "false" })}
                    />
                    <span className="ra-switch-track" />
                  </label>
                </div>
                {data.update_tor === "true" && (
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <label htmlFor="update-tor-proxy" className="form-label" style={{ margin: 0 }}>
                      {t("settingsPage.updateTorProxyLabel")}
                    </label>
                    <input
                      id="update-tor-proxy"
                      type="text"
                      className="form-control"
                      style={{ maxWidth: "200px" }}
                      value={data.update_tor_proxy ?? ""}
                      spellCheck={false}
                      onChange={(e) => setData({ ...data, update_tor_proxy: e.target.value })}
                      onBlur={(e) => handleAutoUpdateChange({ update_tor_proxy: e.target.value.trim() })}
                    />
                    <button type="button" className="btn btn-secondary btn-sm" disabled={torChecking} onClick={handleTorCheck}>
                      <Icon name={torChecking ? "sync" : "verified_user"} size={16} className={torChecking ? "olc-spin" : ""} />
                      {t(torChecking ? "settingsPage.updateTorChecking" : "settingsPage.updateTorCheck")}
                    </button>
                    {torCheck && (
                      <span role="status" style={{ color: torCheck.ok ? "var(--accent-success-text)" : "var(--accent-warning-text)" }}>
                        {torCheck.ok
                          ? t(torCheck.source === "on_demand" ? "settingsPage.updateTorOkOnDemand" : "settingsPage.updateTorOk")
                          : t("settingsPage.updateTorFailed", { error: torCheck.error ?? "" })}
                      </span>
                    )}
                  </div>
                )}
                <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.updateTorHint")}</p>
              </>
            )}
              </>
            )}
  
            {data.store_managed && (
              <div className="olc-anim-in" style={{ display: "flex", flexDirection: "column", gap: "12px", width: "100%", maxWidth: "620px" }}>
                <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeManagedHint")}</p>
                <div className="update-card-banner" style={{ borderLeft: "4px solid var(--accent-text)", boxShadow: "var(--shadow-sm)", display: "flex", flexDirection: "column", gap: "10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700 }}>
                    <Icon
                      name={updateInfo?.store?.state === "available" || updateInfo?.store?.state === "downloaded" ? "system_update" : updateInfo?.store?.state === "failed" ? "error" : "check_circle"}
                      size={18}
                    />
                    <span>
                      {updateInfo?.store?.state === "none" && t("settingsPage.storeUpToDate")}
                      {updateInfo?.store?.state === "available" && `${t("settingsPage.storeAvailable")}${updateInfo.store.version_code ? ` (build ${updateInfo.store.version_code})` : ""}`}
                      {updateInfo?.store?.state === "downloading" && t("settingsPage.storeDownloading")}
                      {updateInfo?.store?.state === "downloaded" && t("settingsPage.storeDownloaded")}
                      {updateInfo?.store?.state === "installing" && t("settingsPage.storeInstalling")}
                      {updateInfo?.store?.state === "failed" && t("settingsPage.storeFailed")}
                      {(!updateInfo?.store || updateInfo.store.state === "unavailable") && (updateInfo?.store?.message || t("settingsPage.storeUnavailable"))}
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                    {updateInfo?.store?.state === "available" && (
                      <button type="button" className="btn btn-primary" disabled={storeBusy} onClick={() => handleStoreAction("start")}>
                        <Icon name="system_update" size={16} /> {t("settingsPage.storeUpdateButton")}
                      </button>
                    )}
                    {updateInfo?.store?.state === "downloaded" && (
                      <button type="button" className="btn btn-primary" disabled={storeBusy} onClick={() => handleStoreAction("complete")}>
                        <Icon name="restart_alt" size={16} /> {t("settingsPage.storeRestartButton")}
                      </button>
                    )}
                    <button type="button" className="btn btn-secondary" disabled={storeBusy} onClick={() => handleStoreAction("open")}>
                      <Icon name="storefront" size={16} /> {t("settingsPage.storeOpenButton")}
                    </button>
                  </div>
                </div>
                <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeAutoHint")}</p>
                <p className="settings-hint" style={{ margin: 0 }}>{t("settingsPage.storeBetaHint")}</p>
              </div>
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
              <div className="olc-anim-in" style={{ marginTop: "4px" }}>
                {updateInfo.has_update ? (
                  <div
                    className="update-card-banner"
                    style={{
                      borderLeft: "4px solid var(--accent-text)",
                      boxShadow: "var(--shadow-sm)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span className="update-badge alert">
                          <Icon name="campaign" size={14} />
                          {updateInfo.is_downgrade ? t("settingsPage.downgradeAvailable") : t("settingsPage.updateAvailable")}
                        </span>
                        <strong style={{ fontSize: "0.95rem" }}>{updateInfo.latest_version}</strong>
                      </div>
                      {updateInfo.html_url && (
                        <a
                          href={updateInfo.html_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-secondary btn-sm"
                          style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "4px" }}
                        >
                          <Icon name="open_in_new" size={14} /> {t("settingsPage.viewOnGithub")}
                        </a>
                      )}
                    </div>
  
                    <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--text-main)" }}>
                      {updateInfo.is_downgrade
                        ? t("settingsPage.downgradeDetail")
                        : updateInfo.release_title || t("settingsPage.updateAvailableDetail")}
                    </p>
  
                    {updateInfo.release_notes && (
                      <div>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          style={{ marginBottom: "8px" }}
                          onClick={() => setShowReleaseNotes((v) => !v)}
                        >
                          <Icon name={showReleaseNotes ? "expand_less" : "expand_more"} size={16} />
                          {t("settingsPage.releaseNotes")}
                        </button>
                        {showReleaseNotes && (
                          <div className="update-notes-box olc-anim-in">
                            <MarkdownView content={updateInfo.release_notes} />
                          </div>
                        )}
                      </div>
                    )}
  
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "4px" }}>
                      {updateInfo.can_auto_apply ? (
                        <button
                          type="button"
                          className="btn btn-primary"
                          style={{ height: "42px", padding: "0 20px", display: "inline-flex", alignItems: "center", gap: "8px" }}
                          onClick={handleApplyUpdate}
                          disabled={applyingUpdate}
                        >
                          {applyingUpdate ? (
                            <>
                              <Icon name="sync" size={16} className="olc-spin" />
                              {t("settingsPage.applyingUpdate")}
                            </>
                          ) : (
                            <>
                              <Icon name="download" size={16} />
                              {updateInfo.is_downgrade ? t("settingsPage.applyDowngrade") : t("settingsPage.applyUpdate")}
                            </>
                          )}
                        </button>
                      ) : (
                        <a
                          href={updateInfo.download_url || updateInfo.html_url || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-primary"
                          style={{ height: "42px", padding: "0 20px", display: "inline-flex", alignItems: "center", gap: "8px", textDecoration: "none" }}
                        >
                          <Icon name="download" size={16} />
                          {updateInfo.asset_name
                            ? `${t("settingsPage.downloadUpdate")} (${updateInfo.asset_name}${updateInfo.asset_size ? ` - ${formatBinarySize(updateInfo.asset_size)}` : ""})`
                            : t("settingsPage.downloadUpdate")}
                        </a>
                      )}
                    </div>
                  </div>
                ) : updateInfo.online ? (
                  <div
                    className="update-card-banner"
                    style={{
                      borderLeft: "4px solid var(--accent-text)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className="update-badge success">
                        <Icon name="check_circle" size={14} />
                        {t("settingsPage.upToDate")}
                      </span>
                      <span style={{ fontSize: "0.9rem", color: "var(--text-main)" }}>
                        {t("settingsPage.upToDateDetail")}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div
                    className="update-card-banner"
                    style={{ borderLeft: "4px solid var(--border-color)" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--text-muted)" }}>
                      <Icon name={updateInfo.error_code === "offline" || !updateInfo.error_code ? "wifi_off" : "info"} size={16} />
                      <span style={{ fontSize: "0.85rem" }}>
                        {updateInfo.message || t("settingsPage.updateError")}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
  
        {confirmingChannel && (
          <div className="modal-overlay">
            <div className="modal-content">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={channelLogoUrl(confirmingChannel)}
                alt=""
                width={72}
                height={72}
                style={{ display: "block", margin: "0 auto", borderRadius: "var(--radius-md)" }}
              />
              <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)", textAlign: "center" }}>
                {t("settingsPage.updateChannelConfirmTitle", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(confirmingChannel)}`) })}
              </h3>
              <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
                {t(`settingsPage.updateChannelConfirmWarning${channelI18nSuffix(confirmingChannel)}`)}
              </p>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setConfirmingChannel(null)} disabled={changingChannel}>{t("common.cancel")}</button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={changingChannel}
                  onClick={() => { const channel = confirmingChannel; setConfirmingChannel(null); handleChannelChange(channel); }}
                >
                  {t("settingsPage.updateChannelConfirmButton", { channel: t(`settingsPage.updateChannel${channelI18nSuffix(confirmingChannel)}`) })}
                </button>
              </div>
            </div>
          </div>
        )}
    </>
  );
}
