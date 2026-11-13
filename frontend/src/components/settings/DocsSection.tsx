"use client";
import React from "react";
import AddressList from "@/components/AddressList";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import { copyText } from "@/lib/clipboard";
import { useIsMobile } from "@/lib/useIsMobile";
import type { ShowToast } from "@/lib/useToast";
import type { SettingsData } from "./types";

const PUBLIC_PAGE_KEYS: { path: string; labelKey: string }[] = [
  { path: "/kiosk", labelKey: "settingsPage.paths.pageKiosk" },
  { path: "/kiosk?channel=network", labelKey: "settingsPage.paths.pageKioskNetwork" },
  { path: "/cinema", labelKey: "settingsPage.paths.pageCinema" },
  { path: "/coach", labelKey: "settingsPage.paths.pageCoach" },
  { path: "/radio?channel=cable", labelKey: "settingsPage.paths.pageRadioCable" },
  { path: "/radio?channel=network", labelKey: "settingsPage.paths.pageRadioNetwork" },
];

const ANDROID_PAGE_KEYS: { path: string; labelKey: string }[] = [
  { path: "/grid", labelKey: "settingsPage.paths.pageGrid" },
];

const PATH_LABEL_KEYS: Record<string, string> = {
  database_url: "settingsPage.paths.database_url",
  media_dir: "settingsPage.paths.media_dir",
  watch_dir: "settingsPage.paths.watch_dir",
  thumbnails_dir: "settingsPage.paths.thumbnails_dir",
  backgrounds_dir: "settingsPage.paths.backgrounds_dir",
  backgrounds_watch_dir: "settingsPage.paths.backgrounds_watch_dir",
  audio_dir: "settingsPage.paths.audio_dir",
  audio_watch_dir: "settingsPage.paths.audio_watch_dir",
  radio_dir: "settingsPage.paths.radio_dir",
  radio_watch_dir: "settingsPage.paths.radio_watch_dir",
  radio_covers_dir: "settingsPage.paths.radio_covers_dir",
  radio_announcements_dir: "settingsPage.paths.radio_announcements_dir",
  branding_dir: "settingsPage.paths.branding_dir",
  logs_dir: "settingsPage.paths.logs_dir",
  subtitles_dir: "settingsPage.paths.subtitles_dir",
};

interface DocsSectionProps {
  hidden: boolean;
  data: SettingsData;
  refreshingNetwork: boolean;
  onRefresh: () => void;
  showToast: ShowToast;
}

export default function DocsSection({ hidden, data, refreshingNetwork, onRefresh, showToast }: DocsSectionProps) {
  const { t } = useAppSettings();
  const isMobile = useIsMobile();
  const handleCopyPath = async (p: string) => {
    if (await copyText(p)) {
      showToast(t("settingsPage.paths.pathCopied"));
    } else {
      showToast(p);
    }
  };

  const handleOpenPath = async (p: string) => {
    try {
      const res = await fetch(getApiUrl("/settings/open-path"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: p }),
      });
      const resData = await res.json().catch(() => ({}));
      if (res.ok) {
        if (resData.status === "android") {
          await copyText(p);
          showToast(resData.message || t("settingsPage.paths.pathCopied"));
        } else {
          showToast(t("settingsPage.paths.folderOpened"));
        }
      } else {
        showToast(errorMessage(resData, t("settingsPage.openFolderError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  return (
      <section className="live-block" id="section-docs" hidden={hidden}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <h3 style={{ margin: 0 }}><Icon name="description" size={18} /> {t("settingsPage.docSection")}</h3>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ minHeight: "36px", padding: "4px 14px", fontSize: "0.85rem", display: "inline-flex", alignItems: "center", gap: "6px" }}
            onClick={onRefresh}
            disabled={refreshingNetwork}
          >
            <Icon name="sync" size={16} className={refreshingNetwork ? "olc-spin" : ""} />
            <span>{refreshingNetwork ? t("settingsPage.refreshingNetwork") : t("settingsPage.refreshNetwork")}</span>
          </button>
        </div>
        <p className="settings-hint" style={{ marginTop: "4px" }}>{t("settingsPage.docHint")}</p>

        <details className="settings-doc-group" open={!isMobile}>
          <summary className="settings-doc-header">
            <Icon name="tv" size={18} />
            <span>{t("settingsPage.paths.localHeading")}</span>
          </summary>
          <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.localHint")}</p>
          <AddressList
            base={`http://127.0.0.1:${data.network.port}`}
            pages={data.deployment_profile === "android" ? [...ANDROID_PAGE_KEYS, ...PUBLIC_PAGE_KEYS] : PUBLIC_PAGE_KEYS}
            t={t}
            onCopy={handleCopyPath}
            copyLabel={t("settingsPage.paths.copyPath")}
          />
        </details>

        <details className="settings-doc-group" open={true}>
          <summary className="settings-doc-header">
            <Icon name="wifi" size={18} />
            <span>{t("settingsPage.paths.networkHeading")}</span>
          </summary>
          <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.networkHint")}</p>
          {(data.network.access ?? []).filter((link) => link.kind === "lan" || link.kind === "vpn").length === 0 && (
            <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.localIpUnavailable")}</p>
          )}
          {(data.network.access ?? [])
            .filter((link) => link.kind !== "loopback")
            .map((link) => (
              <div key={link.url} style={{ marginTop: "10px" }}>
                <div className="settings-path-key" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <Icon name={link.kind === "vpn" ? "vpn_lock" : link.kind === "mdns" ? "dns" : "lan"} size={16} />
                  {link.kind === "mdns"
                    ? t("settingsPage.paths.mdnsUrl")
                    : t(link.kind === "vpn" ? "settingsPage.paths.vpnAddress" : "settingsPage.paths.localIp", { name: link.interface })}
                  {link.kind === "mdns" && (data.network.mdns_status === "failed" || data.network.mdns_status === "unavailable") && (
                    <span title={t("settingsPage.paths.mdnsUnavailableHint")} style={{ display: "inline-flex", color: "var(--accent-warning-text)" }}>
                      <Icon name="warning" size={14} />
                    </span>
                  )}
                </div>
                <AddressList
                  base={link.url}
                  pages={data.deployment_profile === "android" ? [...ANDROID_PAGE_KEYS, ...PUBLIC_PAGE_KEYS] : PUBLIC_PAGE_KEYS}
                  t={t}
                  onCopy={handleCopyPath}
                  copyLabel={t("settingsPage.paths.copyPath")}
                />
              </div>
            ))}
          {data.network.port80_redirect === false && (
            <p className="settings-hint" style={{ margin: "8px 0 0" }}>{t("settingsPage.paths.portRequiredHint", { port: String(data.network.port) })}</p>
          )}
        </details>

        <details className="settings-doc-group" open={!isMobile}>
          <summary className="settings-doc-header">
            <Icon name="folder" size={18} />
            <span>{t("settingsPage.paths.systemHeading")}</span>
          </summary>
          <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.systemHint")}</p>

          <div style={{ margin: "8px 0 14px", padding: "10px 14px", borderRadius: "var(--radius-sm)", background: "color-mix(in srgb, var(--accent-primary) 10%, transparent)", border: "1px solid color-mix(in srgb, var(--accent-primary) 28%, transparent)", display: "flex", alignItems: "center", gap: "10px" }}>
            <Icon name="smartphone" size={18} color="var(--accent-text)" />
            <span style={{ fontSize: "0.85rem", lineHeight: 1.45, color: "var(--text-main)" }}>
              {t("settingsPage.paths.androidStorageNote")}
            </span>
          </div>

          <div className="settings-paths">
            {Object.entries(data.paths).map(([key, value]) => {
              const cleanPath = value.replace(/^sqlite:\/\/\//, "");
              return (
                <div key={key} className="settings-path-row settings-path-row--system">
                  <span className="settings-path-key">{t(PATH_LABEL_KEYS[key] || key)}</span>
                  <span className="settings-path-val settings-path-val--path" title={value}>
                    {value}
                  </span>
                  <div className="settings-path-actions">
                    <button
                      type="button"
                      className="btn btn-secondary olc-press"
                      style={{ height: "30px", padding: "0 10px", fontSize: "0.78rem", display: "inline-flex", alignItems: "center", gap: "4px" }}
                      onClick={() => handleCopyPath(cleanPath)}
                      title={t("settingsPage.paths.copyPath")}
                    >
                      <Icon name="content_copy" size={14} />
                      <span>{t("settingsPage.paths.copyPath")}</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary olc-press"
                      style={{ height: "30px", padding: "0 10px", fontSize: "0.78rem", display: "inline-flex", alignItems: "center", gap: "4px" }}
                      onClick={() => handleOpenPath(cleanPath)}
                      title={t("settingsPage.paths.openFolder")}
                    >
                      <Icon name="folder_open" size={14} />
                      <span>{t("settingsPage.paths.openFolder")}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </details>
      </section>
  );
}
