"use client";
import React from "react";
import ImportDiagnosticsPanel from "@/components/ImportDiagnosticsPanel";
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
import InputsSection from "@/components/settings/InputsSection";
import LogsSection from "@/components/settings/LogsSection";
import SyncSection from "@/components/settings/SyncSection";
import UpdatesSection from "@/components/settings/UpdatesSection";
import SettingsSearch from "@/components/settings/page/SettingsSearch";
import SettingsToast from "@/components/settings/page/SettingsToast";
import { useSettingsData } from "@/components/settings/page/useSettingsData";
import { useSettingsNavigation } from "@/components/settings/page/useSettingsNavigation";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { availableCategories, type SettingsCapability, type SettingsCategoryId } from "@/lib/settingsCategories";
import { getNativeBridge } from "@/lib/nativeBridge";
import { useClientSnapshot } from "@/lib/useClientSnapshot";
import { useToast } from "@/lib/useToast";

export default function SettingsPage() {
  const { t } = useAppSettings();
  const { category, query, setQuery, searching, matched, shows, chooseCategory, openSection } = useSettingsNavigation(t);
  const { data, setData, loading, refreshingNetwork, refreshNetwork } = useSettingsData();
  const { toast, showToast } = useToast(5000);
  const hasNativeBridge = useClientSnapshot(() => getNativeBridge() !== null, false);
  const capabilities = new Set<SettingsCapability>(hasNativeBridge ? ["nativeBridge"] : []);

  if (loading) {
    return <div className="live-empty">{t("common.loading")}</div>;
  }
  if (!data) {
    return <div className="live-empty">{t("settingsPage.loadError")}</div>;
  }

  return (
    <div className="settings-page">
      {toast && <SettingsToast toast={toast} />}

      <PageNav
        tabs={availableCategories(capabilities).map((category) => ({ id: category.id, icon: category.icon, label: t(`settingsPage.cat.${category.id}.label`) }))}
        value={searching && matched.size > 0 ? [...matched][0] : category}
        onChange={(id) => chooseCategory(id as SettingsCategoryId)}
        ariaLabel={t("settingsPage.categoriesLabel")}
      />
      <SettingsSearch query={query} setQuery={setQuery} placeholder={t("settingsPage.searchPlaceholder")} />
      {searching && matched.size === 0 && <div className="live-empty">{t("settingsPage.searchNone")}</div>}

      <AppearanceSection hidden={!shows("section-appearance")} data={data} />
      <DisplaySection hidden={!shows("section-display")} data={data} showToast={showToast} />
      <BrandingSection hidden={!shows("section-branding")} showToast={showToast} />
      <InputsSection hidden={!shows("section-inputs")} showToast={showToast} />
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
