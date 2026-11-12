"use client";
import { errorMessage } from "@/lib/apiError";
import { formatBinarySize } from "@/lib/format";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import BrowserCompatibility from "@/components/BrowserCompatibility";
import MediaNativeSetting from "@/components/MediaNativeSetting";
import { useAppSettings } from "@/lib/AppSettingsContext";
import SegmentedTabs from "@/components/SegmentedTabs";
import PageNav from "@/components/PageNav";
import PlaybackTimingSettings from "@/components/PlaybackTimingSettings";
import { DEFAULT_SETTINGS_CATEGORY, SETTINGS_CATEGORIES, categoryOfSection, matchCategories, type SettingsCategoryId } from "@/lib/settingsCategories";
import { paletteOf, THEME_MODES, THEMES, type ThemeMode } from "@/lib/themePalettes";
import type { Language } from "@/lib/i18n";
import Icon from "@/components/Icon";
import AppLogo from "@/components/AppLogo";
import AddressList from "@/components/AddressList";
import StartOnBootToggle from "@/components/StartOnBootToggle";
import ImportDiagnosticsPanel from "@/components/ImportDiagnosticsPanel";
import { useIsMobile } from "@/lib/useIsMobile";
import { copyText } from "@/lib/clipboard";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { loadMode, saveMode, type GlassMode } from "@/lib/glassQuality";
import DangerSection from "@/components/settings/DangerSection";
import UpdatesSection from "@/components/settings/UpdatesSection";
import type { SettingsData } from "@/components/settings/types";
import { getApiUrl } from "@/lib/apiUrl";
import { useToast } from "@/lib/useToast";



interface LidInfo {
  has_lid: boolean;
  prevent_sleep: boolean;
}

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

export default function SettingsPage() {
  const {
    theme, themeMode, resolvedMode, storedLanguage, languagePending, simplifiedUi, setSimplifiedUi, setTheme, setThemeMode, setLanguage, t,
    hasCustomLogo, activeLogo, setActiveLogo, refreshBranding,
    wiredDisplayMode, displayModeSetting, setDisplayModeSetting, displayExternalCount,
  } = useAppSettings();

  const [category, setCategory] = useState<SettingsCategoryId>(DEFAULT_SETTINGS_CATEGORY);
  const [query, setQuery] = useState("");
  const searching = query.trim().length > 0;
  const matched = useMemo(
    () => matchCategories(query, (id) => ["label", "desc", "keywords"].map((part) => t(`settingsPage.cat.${id}.${part}`)).join(" ")),
    [query, t],
  );
  const shows = (sectionId: string) => {
    const owner = categoryOfSection(sectionId);
    return searching ? owner !== undefined && matched.has(owner) : owner === category;
  };
  const chooseCategory = (id: SettingsCategoryId) => {
    setQuery("");
    setCategory(id);
  };
  const openSection = useCallback((sectionId: string) => {
    const owner = categoryOfSection(sectionId);
    if (owner) {
      setQuery("");
      setCategory(owner);
    }
    window.setTimeout(() => document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }, []);
  useEffect(() => {
    const target = window.location.hash.replace(/^#/, "");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture de l'adresse au montage (lien profond vers une section)
    if (target && categoryOfSection(target)) openSection(target);
  }, [openSection]);
  const isMobile = useIsMobile();
  const [glassMode, setGlassMode] = useState<GlassMode>("auto");
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- relit le réglage mémorisé dans le navigateur au montage
    setGlassMode(loadMode());
  }, []);
  const [data, setData] = useState<SettingsData | null>(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [restartMessage, setRestartMessage] = useState<string | null>(null);
  const restartNow = async () => {
    setRestarting(true);
    setRestartMessage(null);
    try {
      const res = await fetch(getApiUrl("/settings/system/restart"), { method: "POST" });
      setRestartMessage(t(res.ok ? "settingsPage.languageRestarting" : "settingsPage.languageRestartFailed"));
      if (!res.ok) setRestarting(false);
      else {
        window.setTimeout(() => {
          setRestarting(false);
          setRestartMessage(t("settingsPage.languageRestartFailed"));
        }, 30000);
      }
    } catch {
      setRestartMessage(t("settingsPage.languageRestartFailed"));
      setRestarting(false);
    }
  };
  const [loading, setLoading] = useState(true);

  const [refreshingNetwork, setRefreshingNetwork] = useState(false);
  const { toast, showToast } = useToast(5000);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [resetting, setResetting] = useState(false);

  const [exportingBackup, setExportingBackup] = useState(false);
  const [restoringBackup, setRestoringBackup] = useState(false);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);
  const [selectedBackupFile, setSelectedBackupFile] = useState<File | null>(null);


  const [logsRetentionDays, setLogsRetentionDays] = useState<number>(7);
  const [isPurgingLogs, setIsPurgingLogs] = useState<boolean>(false);

  const [lidInfo, setLidInfo] = useState<LidInfo | null>(null);
  const [updatingLid, setUpdatingLid] = useState(false);

  useEffect(() => {
    fetch(getApiUrl("/settings/laptop-lid"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((info) => {
        if (info) setLidInfo(info);
      })
      .catch(() => {});
  }, []);

  const handleToggleLid = async (preventSleep: boolean) => {
    setUpdatingLid(true);
    try {
      const res = await fetch(getApiUrl("/settings/laptop-lid"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prevent_sleep: preventSleep }),
      });
      if (res.ok) {
        const updated: LidInfo = await res.json();
        setLidInfo(updated);
        showToast(t("settingsPage.clamshellApplied"), "success");
      } else {
        showToast(t("settingsPage.clamshellError"), "error");
      }
    } catch {
      showToast(t("settingsPage.clamshellError"), "error");
    } finally {
      setUpdatingLid(false);
    }
  };

  const fetchSettings = useCallback((showIndicator = false) => {
    if (showIndicator) setRefreshingNetwork(true);
    return fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        if (d) {
          setData(d);
          if (typeof d.logs_retention_days === "number") {
            setLogsRetentionDays(d.logs_retention_days);
          }
        }
      })
      .catch(() => {})
      .finally(() => {
        setLoading(false);
        if (showIndicator) setRefreshingNetwork(false);
      });
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial depuis le backend puis rafraîchissement périodique, pas un calcul dérivable au rendu
    fetchSettings();
    const id = setInterval(() => fetchSettings(false), 15000);
    return () => clearInterval(id);
  }, [fetchSettings]);

  const handleLogoUpload = async (file: File) => {
    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(getApiUrl("/settings/logo"), { method: "POST", body: formData });
      if (res.ok) {
        refreshBranding();
        showToast(t("settingsPage.logoUploadSuccess"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(errorMessage(err, t("settingsPage.logoUploadError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleLogoReset = async () => {
    setUploadingLogo(true);
    try {
      const res = await fetch(getApiUrl("/settings/logo"), { method: "DELETE" });
      if (res.ok) {
        refreshBranding();
        showToast(t("settingsPage.logoResetSuccess"));
      } else {
        showToast(t("settingsPage.logoUploadError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleFullReset = async () => {
    setResetting(true);
    try {
      const res = await fetch(getApiUrl("/settings/system/reset"), { method: "POST" });
      if (res.ok) {
        showToast(t("settingsPage.syncResetSuccess"));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(errorMessage(err, t("settingsPage.syncResetError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setResetting(false);
      setShowResetConfirm(false);
    }
  };

  const handleSaveLogsRetention = async (days: number) => {
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ logs_retention_days: days }),
      });
      if (res.ok) {
        showToast(t("settingsPage.retentionSaved"), "success");
      } else {
        showToast(t("settingsPage.saveError"), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    }
  };

  const handlePurgeLogs = async () => {
    if (!window.confirm(t("settingsPage.purgeConfirm"))) return;
    setIsPurgingLogs(true);
    try {
      const res = await fetch(getApiUrl("/settings/logs/purge"), { method: "POST" });
      const body = await res.json();
      if (res.ok) {
        const details = body.details;
        const msg = details
          ? t("settingsPage.purgeDone", { logs: details.purged_logs, metrics: details.purged_metrics })
          : (body.message || t("settingsPage.logsPurgedSuccess"));
        showToast(msg, "success");
      } else {
        showToast(errorMessage(body, t("settingsPage.saveError")), "error");
      }
    } catch {
      showToast(t("common.networkError"), "error");
    } finally {
      setIsPurgingLogs(false);
    }
  };

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

  const handleExportBackup = () => {
    setExportingBackup(true);
    const url = getApiUrl("/settings/backup/export");
    const a = document.createElement("a");
    a.href = url;
    a.download = `bobine-backup-${new Date().toISOString().slice(0, 10)}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => setExportingBackup(false), 2000);
  };

  const handleSelectBackupFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedBackupFile(file);
      setShowRestoreConfirm(true);
    }
    e.target.value = "";
  };

  const handleRestoreBackup = async () => {
    if (!selectedBackupFile) return;
    setRestoringBackup(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedBackupFile);
      const res = await fetch(getApiUrl("/settings/backup/restore"), {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        showToast(t("settingsPage.restoreSuccess"), "success");
        setShowRestoreConfirm(false);
        setSelectedBackupFile(null);
      } else {
        const err = await res.json().catch(() => null);
        showToast(errorMessage(err, t("settingsPage.restoreError")), "error");
      }
    } catch {
      showToast(t("settingsPage.restoreError"), "error");
    } finally {
      setRestoringBackup(false);
    }
  };

  if (loading) {
    return <div className="live-empty">{t("common.loading")}</div>;
  }
  if (!data) {
    return <div className="live-empty">{t("settingsPage.loadError")}</div>;
  }

  return (
    <div className="settings-page">
      {toast && (
        <div
          className={`toast ${toast.type} ${toast.onClick ? "clickable olc-press" : ""}`}
          onClick={toast.onClick}
          style={{ cursor: toast.onClick ? "pointer" : "default" }}
          role={toast.onClick ? "button" : undefined}
          tabIndex={toast.onClick ? 0 : undefined}
        >
          {toast.type === "warning" && <Icon name="system_update" size={18} color="var(--accent-text)" />}
          <span>{toast.message}</span>
          {toast.onClick && <Icon name="arrow_downward" size={16} />}
        </div>
      )}

      <PageNav
        tabs={SETTINGS_CATEGORIES.map((category) => ({ id: category.id, icon: category.icon, label: t(`settingsPage.cat.${category.id}.label`) }))}
        value={searching && matched.size > 0 ? [...matched][0] : category}
        onChange={(id) => chooseCategory(id as SettingsCategoryId)}
        ariaLabel={t("settingsPage.categoriesLabel")}
      />
      <div className="settings-search-row">
        <label className="settings-search">
          <Icon name="search" size={18} />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("settingsPage.searchPlaceholder")}
            aria-label={t("settingsPage.searchPlaceholder")}
          />
        </label>
      </div>
      {searching && matched.size === 0 && <div className="live-empty">{t("settingsPage.searchNone")}</div>}

      <section className="live-block" id="section-appearance" hidden={!shows("section-appearance")}>
        <h3><Icon name="palette" size={18} /> {t("settingsPage.appearanceSection")}</h3>
        <div className="form-group">
          <label className="form-label">{t("settingsPage.themeLabel")}</label>

          <SegmentedTabs
            ariaLabel={t("settingsPage.themeModeLabel")}
            value={themeMode}
            onChange={(id) => setThemeMode(id as ThemeMode)}
            tabs={THEME_MODES.map((mode) => ({
              id: mode,
              icon: mode === "auto" ? "brightness_auto" : mode === "light" ? "light_mode" : "dark_mode",
              label: t(`settingsPage.themeMode${mode === "auto" ? "Auto" : mode === "light" ? "Light" : "Dark"}`),
            }))}
          />
          <p className="settings-hint">{t("settingsPage.themeModeHint")}</p>

          <div className="theme-picker-grid">
            {THEMES.map((option) => {
              const palette = paletteOf(option.id, resolvedMode);
              return (
                <button
                  key={option.id}
                  type="button"
                  className={`theme-picker-card ${theme === option.id ? "active" : ""}`}
                  aria-pressed={theme === option.id}
                  onClick={() => setTheme(option.id)}
                >
                  <div className="theme-picker-swatch">
                    {[palette.bg, palette.surface, palette.accent, palette.text].map((color, i) => (
                      <span key={i} style={{ background: color }} />
                    ))}
                  </div>
                  <span className="theme-picker-name">{t(option.labelKey)}</span>
                </button>
              );
            })}
          </div>

          <p className="settings-hint">{t("settingsPage.themeHint")}</p>
        </div>

        <div className="form-group" style={{ maxWidth: "320px" }}>
          <label className="form-label">{t("settingsPage.glassLabel")}</label>
          <ResponsiveSelect
            className="form-control"
            value={glassMode}
            onChange={(value) => { setGlassMode(value as GlassMode); saveMode(value as GlassMode); }}
            title={t("settingsPage.glassLabel")}
            options={[
              { value: "auto", label: t("settingsPage.glassAuto") },
              { value: "full", label: t("settingsPage.glassFull") },
              { value: "reduced", label: t("settingsPage.glassReduced") },
              { value: "off", label: t("settingsPage.glassOff") },
            ]}
          />
          <p className="settings-hint">{t("settingsPage.glassHint")}</p>
        </div>

        <div className="form-group" style={{ maxWidth: "320px" }}>
          <label className="form-label">{t("settingsPage.languageLabel")}</label>
          <ResponsiveSelect
            className="form-control"
            value={storedLanguage}
            onChange={(value) => setLanguage(value as Language)}
            title={t("settingsPage.languageLabel")}
            options={[
              { value: "fr", label: t("settingsPage.languageFr") },
              { value: "en", label: t("settingsPage.languageEn") },
            ]}
          />
          <p className="settings-hint">{t("settingsPage.languageHint")}</p>
          {languagePending && (
            <div className="settings-hint" role="status" style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
              <span>{t("settingsPage.languagePending", { language: storedLanguage === "fr" ? t("settingsPage.languageFr") : t("settingsPage.languageEn") })}</span>
              <button type="button" className="btn btn-secondary" onClick={() => void restartNow()} disabled={restarting}>
                {t("settingsPage.languageRestartNow")}
              </button>
              {data && data.restart_guaranteed === false && <span>{t("settingsPage.restartNotGuaranteed")}</span>}
              {restartMessage && <span>{restartMessage}</span>}
            </div>
          )}
        </div>

        <div className="form-group" style={{ maxWidth: "520px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "16px", flexWrap: "wrap" }}>
            <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>{t("settingsPage.simplifiedUiLabel")}</span>
            <label className="ra-switch" title={t("settingsPage.simplifiedUiLabel")}>
              <input type="checkbox" checked={simplifiedUi} onChange={(e) => setSimplifiedUi(e.target.checked)} />
              <span className="ra-switch-track" />
            </label>
          </div>
          <p className="settings-hint">{t("settingsPage.simplifiedUiHint")}</p>
        </div>
      </section>

      <section className="live-block" id="section-display" hidden={!shows("section-display")}>
        <h3><Icon name="tv" size={18} /> {t("settingsPage.wiredDisplaySection")}</h3>
        <p className="settings-hint" style={{ marginTop: "-8px", marginBottom: "16px" }}>
          {t("settingsPage.wiredDisplaySubtitle")}
        </p>

        <div className="form-group">
          <label className="form-label">{t("settingsPage.wiredDisplayModeLabel")}</label>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px", marginTop: "8px" }}>
            <button
              type="button"
              className={`theme-picker-card ${displayModeSetting === "auto" ? "active" : ""}`}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "16px",
                textAlign: "left",
                height: "auto",
                gap: "8px",
              }}
              onClick={() => {
                setDisplayModeSetting("auto");
                showToast(t("settingsPage.savedToast"), "success");
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
                <div style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "var(--radius-sm)",
                  background: displayModeSetting === "auto" ? "var(--accent-primary)" : "var(--bg-surface-hover)",
                  color: displayModeSetting === "auto" ? "var(--accent-primary-fg)" : "var(--text-main)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <Icon name="autorenew" size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <strong style={{ display: "block", fontSize: "0.95rem" }}>
                    {t("settingsPage.wiredDisplayModeAuto")}
                  </strong>
                </div>
                {displayModeSetting === "auto" && (
                  <span style={{ color: "var(--accent-text)", display: "flex", alignItems: "center" }}>
                    <Icon name="check_circle" size={18} />
                  </span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                {t("settingsPage.wiredDisplayModeAutoDesc")}
              </p>
              <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--accent-text)", lineHeight: 1.4 }}>
                {displayExternalCount === null
                  ? t("settingsPage.wiredDisplayAutoNoReport")
                  : t("settingsPage.wiredDisplayAutoDetected", {
                      count: displayExternalCount,
                      mode: wiredDisplayMode === "dual_screen" ? t("settingsPage.wiredDisplayModeDual") : t("settingsPage.wiredDisplayModeHeadless"),
                    })}
              </p>
            </button>

            <button
              type="button"
              className={`theme-picker-card ${displayModeSetting === "headless" ? "active" : ""}`}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "16px",
                textAlign: "left",
                height: "auto",
                gap: "8px",
              }}
              onClick={() => {
                setDisplayModeSetting("headless");
                showToast(t("settingsPage.savedToast"), "success");
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
                <div style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "var(--radius-sm)",
                  background: displayModeSetting === "headless" ? "var(--accent-primary)" : "var(--bg-surface-hover)",
                  color: displayModeSetting === "headless" ? "var(--accent-primary-fg)" : "var(--text-main)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <Icon name="desktop_windows" size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <strong style={{ display: "block", fontSize: "0.95rem" }}>
                    {t("settingsPage.wiredDisplayModeHeadless")}
                  </strong>
                </div>
                {displayModeSetting === "headless" && (
                  <span style={{ color: "var(--accent-text)", display: "flex", alignItems: "center" }}>
                    <Icon name="check_circle" size={18} />
                  </span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                {t("settingsPage.wiredDisplayModeHeadlessDesc")}
              </p>
            </button>

            <button
              type="button"
              className={`theme-picker-card ${displayModeSetting === "dual_screen" ? "active" : ""}`}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "16px",
                textAlign: "left",
                height: "auto",
                gap: "8px",
              }}
              onClick={() => {
                setDisplayModeSetting("dual_screen");
                showToast(t("settingsPage.savedToast"), "success");
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
                <div style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "var(--radius-sm)",
                  background: displayModeSetting === "dual_screen" ? "var(--accent-primary)" : "var(--bg-surface-hover)",
                  color: displayModeSetting === "dual_screen" ? "var(--accent-primary-fg)" : "var(--text-main)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <Icon name="view_quilt" size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <strong style={{ display: "block", fontSize: "0.95rem" }}>
                    {t("settingsPage.wiredDisplayModeDual")}
                  </strong>
                </div>
                {displayModeSetting === "dual_screen" && (
                  <span style={{ color: "var(--accent-text)", display: "flex", alignItems: "center" }}>
                    <Icon name="check_circle" size={18} />
                  </span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                {t("settingsPage.wiredDisplayModeDualDesc")}
              </p>
            </button>
          </div>

          <div
            style={{
              marginTop: "12px",
              padding: "12px 16px",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "var(--radius-md)",
              display: "flex",
              alignItems: "flex-start",
              gap: "12px",
            }}
          >
            <div style={{ color: "var(--accent-text)", marginTop: "1px", flexShrink: 0 }}>
              <Icon name="info" size={20} />
            </div>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
              {t("settingsPage.wiredDisplayGridCableOnlyNote")}
            </p>
          </div>

          {wiredDisplayMode === "dual_screen" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "16px" }} className="olc-anim-in">
              <a
                href="/grid"
                target="_blank"
                rel="noopener noreferrer"
                className="wired-display-action-card olc-card-hover"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-surface-elevated)",
                  border: "1px solid var(--border-color)",
                  textDecoration: "none",
                  color: "inherit",
                  gap: "16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                  <div style={{
                    width: "42px",
                    height: "42px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--accent-primary)",
                    color: "var(--accent-primary-fg)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}>
                    <Icon name="touch_app" size={22} />
                  </div>
                  <div>
                    <strong style={{ display: "block", fontSize: "0.98rem", color: "var(--text-main)", marginBottom: "3px" }}>
                      {t("settingsPage.wiredDisplayOpenGrid")}
                    </strong>
                    <span style={{ fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                      {t("settingsPage.wiredDisplayOpenGridDesc")}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--accent-text)", fontWeight: 700, fontSize: "0.9rem", flexShrink: 0 }}>
                  <span>{t("settingsPage.wiredDisplayOpenGrid")}</span>
                  <Icon name="open_in_new" size={16} />
                </div>
              </a>

              <a
                href="/cinema"
                target="_blank"
                rel="noopener noreferrer"
                className="wired-display-action-card olc-card-hover"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 20px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-surface-elevated)",
                  border: "1px solid var(--border-color)",
                  textDecoration: "none",
                  color: "inherit",
                  gap: "16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                  <div style={{
                    width: "42px",
                    height: "42px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--bg-surface-hover)",
                    color: "var(--text-main)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}>
                    <Icon name="tv" size={22} />
                  </div>
                  <div>
                    <strong style={{ display: "block", fontSize: "0.98rem", color: "var(--text-main)", marginBottom: "3px" }}>
                      {t("settingsPage.wiredDisplayOpenCinema")}
                    </strong>
                    <span style={{ fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>
                      {t("settingsPage.wiredDisplayOpenCinemaDesc")}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--accent-text)", fontWeight: 700, fontSize: "0.9rem", flexShrink: 0 }}>
                  <span>{t("settingsPage.wiredDisplayOpenCinema")}</span>
                  <Icon name="open_in_new" size={16} />
                </div>
              </a>
            </div>
          )}

          {lidInfo?.has_lid && (
            <div
              style={{
                marginTop: "16px",
                padding: "16px 20px",
                borderRadius: "var(--radius-md)",
                background: "var(--bg-surface-elevated)",
                border: "1px solid var(--border-color)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "16px",
                flexWrap: "wrap",
              }}
            >
              <div style={{ flex: "1 1 280px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, fontSize: "0.95rem", color: "var(--text-main)" }}>
                  <Icon name="laptop" size={20} />
                  <span>{t("settingsPage.clamshellToggle")}</span>
                </div>
                <p className="settings-hint" style={{ margin: "4px 0 0 28px", fontSize: "0.85rem" }}>
                  {t("settingsPage.clamshellDesc")}
                </p>
              </div>
              <div
                style={{
                  display: "inline-flex",
                  borderRadius: "var(--radius-md)",
                  overflow: "hidden",
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-surface-elevated)",
                }}
              >
                <button
                  type="button"
                  className={`btn btn-sm ${lidInfo.prevent_sleep ? "btn-primary" : "btn-secondary"}`}
                  style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 }}
                  onClick={() => handleToggleLid(true)}
                  disabled={updatingLid}
                >
                  {t("common.yes")}
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${!lidInfo.prevent_sleep ? "btn-primary" : "btn-secondary"}`}
                  style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 16px", fontWeight: 700 }}
                  onClick={() => handleToggleLid(false)}
                  disabled={updatingLid}
                >
                  {t("common.no")}
                </button>
              </div>
            </div>
          )}

          {data?.deployment_profile === "android" && (
            <p className="settings-hint" style={{ marginTop: "12px" }}>
              {t("settingsPage.wiredDisplayTabletHint")}
            </p>
          )}
        </div>
      </section>

      <section className="live-block" id="section-branding" hidden={!shows("section-branding")}>
        <h3><Icon name="image" size={18} /> {t("settingsPage.brandingSection")}</h3>
        <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "24px", flexWrap: "wrap" }}>
          <div
            style={{
              width: "180px",
              height: "84px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "var(--radius-md)",
              padding: "10px",
              flexShrink: 0,
              overflow: "hidden",
            }}
          >
            <AppLogo size={54} />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px", flexGrow: 1, minWidth: "260px" }}>
            {hasCustomLogo && (
              <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                <span className="form-label" style={{ margin: 0, fontSize: "0.85rem" }}>
                  {t("settingsPage.activeLogoLabel")}
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
                  <button
                    type="button"
                    className={`btn btn-sm ${activeLogo === "default" ? "btn-primary" : "btn-secondary"}`}
                    style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px" }}
                    onClick={() => setActiveLogo("default")}
                  >
                    {t("settingsPage.logoBobine")}
                  </button>
                  <button
                    type="button"
                    className={`btn btn-sm ${activeLogo === "custom" ? "btn-primary" : "btn-secondary"}`}
                    style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px" }}
                    onClick={() => setActiveLogo("custom")}
                  >
                    {t("settingsPage.logoCustom")}
                  </button>
                </div>
              </div>
            )}

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
              <label className="btn btn-secondary" style={{ height: "38px", cursor: uploadingLogo ? "wait" : "pointer" }}>
                <Icon name="upload" size={16} /> {hasCustomLogo ? t("settingsPage.logoUploadReplace") : t("settingsPage.logoUploadLabel")}
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  style={{ display: "none" }}
                  disabled={uploadingLogo}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleLogoUpload(file);
                    e.target.value = "";
                  }}
                />
              </label>

              {hasCustomLogo && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ height: "38px", color: "var(--accent-error-text)" }}
                  onClick={() => {
                    if (window.confirm(t("settingsPage.logoDeleteConfirm"))) {
                      handleLogoReset();
                    }
                  }}
                  disabled={uploadingLogo}
                  title={t("settingsPage.logoDeleteButton")}
                >
                  <Icon name="delete" size={16} /> {t("settingsPage.logoDeleteButton")}
                </button>
              )}
            </div>

            <p className="settings-hint" style={{ margin: 0 }}>
              {t("settingsPage.logoHint")}
            </p>
          </div>
        </div>
      </section>

      <UpdatesSection t={t} data={data} setData={setData} showToast={showToast} hidden={!shows("updates-section")} openSection={openSection} />
      <div id="section-playback" hidden={!shows("section-playback")}>
      <PlaybackTimingSettings />
      <BrowserCompatibility />

      <MediaNativeSetting />
      </div>

      <section className="live-block" id="section-backup" hidden={!shows("section-backup")}>
        <h3><Icon name="archive" size={18} /> {t("settingsPage.backupSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.backupHint")}</p>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ minHeight: "44px", display: "inline-flex", alignItems: "center", gap: "8px" }}
            onClick={handleExportBackup}
            disabled={exportingBackup}
          >
            <Icon name="download" size={16} />
            {exportingBackup ? t("settingsPage.exportingBackup") : t("settingsPage.exportBackup")}
          </button>

          <label
            className="btn btn-secondary"
            style={{ minHeight: "44px", display: "inline-flex", alignItems: "center", gap: "8px", cursor: "pointer", margin: 0 }}
          >
            <Icon name="upload" size={16} />
            {t("settingsPage.restoreBackup")}
            <input
              type="file"
              accept=".zip"
              style={{ display: "none" }}
              onChange={handleSelectBackupFile}
            />
          </label>
        </div>
      </section>

      <section className="live-block" id="section-sync" hidden={!shows("section-sync")}>
        <h3><Icon name="sync" size={18} /> {t("settingsPage.syncSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.syncHint")}</p>
        <button type="button" className="btn btn-secondary" style={{ height: "44px", alignSelf: "flex-start" }} onClick={() => setShowResetConfirm(true)}>
          <Icon name="sync" size={16} /> {t("settingsPage.syncResetButton")}
        </button>
      </section>

      <section className="live-block" id="section-logs" hidden={!shows("section-logs")}>
        <h3><Icon name="auto_delete" size={18} /> {t("settingsPage.logsMaintenanceSection")}</h3>
        <p className="settings-hint" style={{ marginTop: 0 }}>{t("settingsPage.logsMaintenanceHint")}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
            <label style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-main)" }}>
              {t("settingsPage.logsRetentionDaysLabel")} :
            </label>
            <input
              type="number"
              min={1}
              max={365}
              value={logsRetentionDays}
              onChange={(e) => setLogsRetentionDays(Math.max(1, parseInt(e.target.value) || 1))}
              onBlur={() => handleSaveLogsRetention(logsRetentionDays)}
              style={{
                width: "80px",
                padding: "6px 10px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-color)",
                background: "var(--bg-surface-elevated)",
                color: "var(--text-main)",
                fontSize: "0.95rem",
                fontWeight: 700,
                textAlign: "center",
              }}
            />
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              {t("settingsPage.logsRetentionDaysHint")}
            </span>
          </div>
          <div>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ height: "42px", display: "inline-flex", alignItems: "center", gap: "8px" }}
              onClick={handlePurgeLogs}
              disabled={isPurgingLogs}
            >
              <Icon name="delete_sweep" size={18} />
              {isPurgingLogs ? t("settingsPage.logsPurging") : t("settingsPage.logsPurgeNow")}
            </button>
          </div>
        </div>
      </section>

      <div id="section-diagnostics" hidden={!shows("section-diagnostics")}>
      <ImportDiagnosticsPanel />
      </div>

      <div id="section-startup" hidden={!shows("section-startup")}>
      <StartOnBootToggle />
      </div>

      <section className="live-block" id="section-docs" hidden={!shows("section-docs")}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <h3 style={{ margin: 0 }}><Icon name="description" size={18} /> {t("settingsPage.docSection")}</h3>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ minHeight: "36px", padding: "4px 14px", fontSize: "0.85rem", display: "inline-flex", alignItems: "center", gap: "6px" }}
            onClick={() => fetchSettings(true)}
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

      <DangerSection
        hidden={!shows("section-danger")}
        deploymentProfile={data.deployment_profile}
        showToast={showToast}
      />

      {showResetConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--text-main)" }}>{t("settingsPage.syncResetButton")}</h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>{t("settingsPage.syncResetConfirm")}</p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowResetConfirm(false)} disabled={resetting}>{t("common.cancel")}</button>
              <button type="button" className="btn btn-primary" style={{ backgroundColor: "var(--accent-error)" }} onClick={handleFullReset} disabled={resetting}>
                {resetting ? t("settingsPage.syncResetInProgress") : t("settingsPage.syncResetButton")}
              </button>
            </div>
          </div>
        </div>
      )}


      {showRestoreConfirm && selectedBackupFile && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 style={{ fontSize: "1.1rem", fontWeight: 800, margin: 0, color: "var(--accent-text)" }}>
              <Icon name="upload" size={20} /> {t("settingsPage.restoreBackup")}
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
              {t("settingsPage.restoreBackupConfirmText")}
            </p>
            <div style={{ padding: "10px 14px", background: "var(--bg-surface-hover)", borderRadius: "8px", fontSize: "0.85rem", border: "1px solid var(--border-color)" }}>
              <strong>{t("settingsPage.restoreBackupPrompt")}</strong>
              <div style={{ marginTop: "4px", fontFamily: "var(--font-mono, monospace)" }}>
                {selectedBackupFile.name} ({formatBinarySize(selectedBackupFile.size)})
              </div>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => { setShowRestoreConfirm(false); setSelectedBackupFile(null); }}
                disabled={restoringBackup}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleRestoreBackup}
                disabled={restoringBackup}
              >
                {restoringBackup ? t("settingsPage.restoringBackup") : t("settingsPage.restoreBackup")}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
