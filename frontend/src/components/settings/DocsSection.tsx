"use client";
import React from "react";
import AddressList from "@/components/AddressList";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useIsMobile } from "@/lib/useIsMobile";
import type { ShowToast } from "@/lib/useToast";
import type { SettingsData } from "./types";
import NetworkAccessList from "./docs/NetworkAccessList";
import { pagesFor } from "./docs/pages";
import SystemPaths from "./docs/SystemPaths";
import { usePathActions } from "./docs/usePathActions";

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
  const { handleCopyPath, handleOpenPath } = usePathActions(showToast);

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
            pages={pagesFor(data.deployment_profile)}
            t={t}
            onCopy={handleCopyPath}
            copyLabel={t("settingsPage.paths.copyPath")}
          />
        </details>
        <NetworkAccessList data={data} onCopy={handleCopyPath} />
        <SystemPaths data={data} open={!isMobile} onCopy={handleCopyPath} onOpen={handleOpenPath} />
      </section>
  );
}
