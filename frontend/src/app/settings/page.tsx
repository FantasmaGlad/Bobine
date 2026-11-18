"use client";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import ImportDiagnosticsPanel from "@/components/ImportDiagnosticsPanel";
import Icon from "@/components/Icon";
import MediaNativeSetting from "@/components/MediaNativeSetting";
import PageNav from "@/components/PageNav";
import PlaybackTimingSettings from "@/components/PlaybackTimingSettings";
import BrowserCompatibility from "@/components/BrowserCompatibility";
import StartOnBootToggle from "@/components/StartOnBootToggle";
import AppearanceSection from "@/components/settings/AppearanceSection";
import BackupSection from "@/components/settings/BackupSection";
import BrandingSection from "@/components/settings/BrandingSection";
import DangerSection from "@/components/settings/DangerSection";
import DisplaySection from "@/components/settings/DisplaySection";
import DocsSection from "@/components/settings/DocsSection";
import LogsSection from "@/components/settings/LogsSection";
import SyncSection from "@/components/settings/SyncSection";
import UpdatesSection from "@/components/settings/UpdatesSection";
import type { SettingsData } from "@/components/settings/types";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { DEFAULT_SETTINGS_CATEGORY, SETTINGS_CATEGORIES, categoryOfSection, matchCategories, type SettingsCategoryId } from "@/lib/settingsCategories";
import { useClientSnapshot } from "@/lib/useClientSnapshot";
import { useToast } from "@/lib/useToast";

export default function SettingsPage() {
  const { t } = useAppSettings();
  const linkedSection = useClientSnapshot(() => window.location.hash.replace(/^#/, ""), "");
  const [chosenCategory, setCategory] = useState<SettingsCategoryId | null>(null);
  const category = chosenCategory ?? categoryOfSection(linkedSection) ?? DEFAULT_SETTINGS_CATEGORY;
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
    if (!linkedSection || !categoryOfSection(linkedSection)) return;
    window.setTimeout(() => document.getElementById(linkedSection)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }, [linkedSection]);
  const [data, setData] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingNetwork, setRefreshingNetwork] = useState(false);
  const { toast, showToast } = useToast(5000);

  const fetchSettings = useCallback(() => fetch(getApiUrl("/settings"), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : null))
    .then((d) => {
      if (d) setData(d);
    })
    .catch(() => {})
    .finally(() => setLoading(false)), []);

  const refreshNetwork = () => {
    setRefreshingNetwork(true);
    void fetchSettings().finally(() => setRefreshingNetwork(false));
  };

  useEffect(() => {
    void fetchSettings();
    const id = setInterval(() => void fetchSettings(), 15000);
    return () => clearInterval(id);
  }, [fetchSettings]);

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

      <AppearanceSection hidden={!shows("section-appearance")} data={data} />
      <DisplaySection hidden={!shows("section-display")} data={data} showToast={showToast} />
      <BrandingSection hidden={!shows("section-branding")} showToast={showToast} />
      <UpdatesSection hidden={!shows("updates-section")} t={t} data={data} setData={setData} showToast={showToast} openSection={openSection} />
      <div id="section-playback" hidden={!shows("section-playback")}>
      <PlaybackTimingSettings />
      <BrowserCompatibility />

      <MediaNativeSetting />
      </div>

      <BackupSection hidden={!shows("section-backup")} showToast={showToast} />
      <SyncSection hidden={!shows("section-sync")} showToast={showToast} />
      <LogsSection hidden={!shows("section-logs")} initialDays={data.logs_retention_days ?? 7} showToast={showToast} />
      <div id="section-diagnostics" hidden={!shows("section-diagnostics")}>
      <ImportDiagnosticsPanel />
      </div>

      <div id="section-startup" hidden={!shows("section-startup")}>
      <StartOnBootToggle />
      </div>

      <DocsSection hidden={!shows("section-docs")} data={data} refreshingNetwork={refreshingNetwork} onRefresh={refreshNetwork} showToast={showToast} />

      <DangerSection
        hidden={!shows("section-danger")}
        deploymentProfile={data.deployment_profile}
        showToast={showToast}
      />
    </div>
  );
}
