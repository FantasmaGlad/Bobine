"use client";
import React, { useState } from "react";
import Icon from "@/components/Icon";
import { errorMessage } from "@/lib/apiError";
import { getApiUrl } from "@/lib/apiUrl";
import type { SettingsData } from "./types";

interface TorUpdateSettingsProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  data: SettingsData;
  setData: React.Dispatch<React.SetStateAction<SettingsData | null>>;
  handleAutoUpdateChange: (patch: { update_tor?: "true" | "false"; update_tor_proxy?: string }) => void;
}

export default function TorUpdateSettings({ t, data, setData, handleAutoUpdateChange }: TorUpdateSettingsProps) {
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

  return (
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
  );
}
