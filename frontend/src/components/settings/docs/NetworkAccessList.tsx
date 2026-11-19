"use client";

import AddressList from "@/components/AddressList";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { SettingsData } from "../types";
import { pagesFor } from "./pages";

type Link = NonNullable<SettingsData["network"]["access"]>[number];

function LinkLabel({ link, mdnsStatus }: { link: Link; mdnsStatus: SettingsData["network"]["mdns_status"] }) {
  const { t } = useAppSettings();
  return (
    <div className="settings-path-key" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <Icon name={link.kind === "vpn" ? "vpn_lock" : link.kind === "mdns" ? "dns" : "lan"} size={16} />
      {link.kind === "mdns"
        ? t("settingsPage.paths.mdnsUrl")
        : t(link.kind === "vpn" ? "settingsPage.paths.vpnAddress" : "settingsPage.paths.localIp", { name: link.interface })}
      {link.kind === "mdns" && (mdnsStatus === "failed" || mdnsStatus === "unavailable") && (
        <span title={t("settingsPage.paths.mdnsUnavailableHint")} style={{ display: "inline-flex", color: "var(--accent-warning-text)" }}>
          <Icon name="warning" size={14} />
        </span>
      )}
    </div>
  );
}

export default function NetworkAccessList({ data, onCopy }: { data: SettingsData; onCopy: (path: string) => void }) {
  const { t } = useAppSettings();
  const access = data.network.access ?? [];
  return (
    <details className="settings-doc-group" open={true}>
      <summary className="settings-doc-header">
        <Icon name="wifi" size={18} />
        <span>{t("settingsPage.paths.networkHeading")}</span>
      </summary>
      <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.networkHint")}</p>
      {access.filter((link) => link.kind === "lan" || link.kind === "vpn").length === 0 && (
        <p className="settings-hint" style={{ margin: "2px 0 6px" }}>{t("settingsPage.paths.localIpUnavailable")}</p>
      )}
      {access
        .filter((link) => link.kind !== "loopback")
        .map((link) => (
          <div key={link.url} style={{ marginTop: "10px" }}>
            <LinkLabel link={link} mdnsStatus={data.network.mdns_status} />
            <AddressList base={link.url} pages={pagesFor(data.deployment_profile)} t={t} onCopy={onCopy} copyLabel={t("settingsPage.paths.copyPath")} />
          </div>
        ))}
      {data.network.port80_redirect === false && (
        <p className="settings-hint" style={{ margin: "8px 0 0" }}>{t("settingsPage.paths.portRequiredHint", { port: String(data.network.port) })}</p>
      )}
    </details>
  );
}
