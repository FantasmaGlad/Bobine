"use client";
import { useEffect, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import type { SettingsData } from "@/components/settings/types";
import { getApiUrl } from "@/lib/apiUrl";
import type { ShowToast } from "@/lib/useToast";

interface LidInfo {
  has_lid: boolean;
  prevent_sleep: boolean;
}

interface DisplaySectionProps {
  hidden: boolean;
  data: SettingsData;
  showToast: ShowToast;
}

export default function DisplaySection({ hidden, data, showToast }: DisplaySectionProps) {
  const { t, wiredDisplayMode, displayModeSetting, setDisplayModeSetting, displayExternalCount } = useAppSettings();

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

  return (
    <section className="live-block" id="section-display" hidden={hidden}>
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

  );
}
