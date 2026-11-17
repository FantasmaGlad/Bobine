"use client";
import { useAppSettings } from "@/lib/AppSettingsContext";
import Icon from "@/components/Icon";
import DisplayLinkCard from "@/components/settings/display/DisplayLinkCard";
import DisplayModeCard from "@/components/settings/display/DisplayModeCard";
import LidSetting from "@/components/settings/display/LidSetting";
import type { SettingsData } from "@/components/settings/types";
import type { DisplayModeSetting } from "@/lib/settings/types";
import type { ShowToast } from "@/lib/useToast";

interface DisplaySectionProps {
  hidden: boolean;
  data: SettingsData;
  showToast: ShowToast;
}

const NOTE = {
  marginTop: "12px",
  padding: "12px 16px",
  background: "var(--bg-surface-elevated)",
  border: "1px solid var(--border-color)",
  borderRadius: "var(--radius-md)",
  display: "flex",
  alignItems: "flex-start",
  gap: "12px",
} as const;

export default function DisplaySection({ hidden, data, showToast }: DisplaySectionProps) {
  const { t, wiredDisplayMode, displayModeSetting, setDisplayModeSetting, displayExternalCount } = useAppSettings();
  const select = (mode: DisplayModeSetting) => () => {
    setDisplayModeSetting(mode);
    showToast(t("settingsPage.savedToast"), "success");
  };
  const autoDetail = displayExternalCount === null
    ? t("settingsPage.wiredDisplayAutoNoReport")
    : t("settingsPage.wiredDisplayAutoDetected", {
        count: displayExternalCount,
        mode: wiredDisplayMode === "dual_screen" ? t("settingsPage.wiredDisplayModeDual") : t("settingsPage.wiredDisplayModeHeadless"),
      });

  return (
    <section className="live-block" id="section-display" hidden={hidden}>
      <h3><Icon name="tv" size={18} /> {t("settingsPage.wiredDisplaySection")}</h3>
      <p className="settings-hint" style={{ marginTop: "-8px", marginBottom: "16px" }}>
        {t("settingsPage.wiredDisplaySubtitle")}
      </p>

      <div className="form-group">
        <label className="form-label">{t("settingsPage.wiredDisplayModeLabel")}</label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px", marginTop: "8px" }}>
          <DisplayModeCard active={displayModeSetting === "auto"} icon="autorenew" title={t("settingsPage.wiredDisplayModeAuto")}
            description={t("settingsPage.wiredDisplayModeAutoDesc")} detail={autoDetail} onSelect={select("auto")} />
          <DisplayModeCard active={displayModeSetting === "headless"} icon="desktop_windows" title={t("settingsPage.wiredDisplayModeHeadless")}
            description={t("settingsPage.wiredDisplayModeHeadlessDesc")} onSelect={select("headless")} />
          <DisplayModeCard active={displayModeSetting === "dual_screen"} icon="view_quilt" title={t("settingsPage.wiredDisplayModeDual")}
            description={t("settingsPage.wiredDisplayModeDualDesc")} onSelect={select("dual_screen")} />
        </div>

        <div style={NOTE}>
          <div style={{ color: "var(--accent-text)", marginTop: "1px", flexShrink: 0 }}>
            <Icon name="info" size={20} />
          </div>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
            {t("settingsPage.wiredDisplayGridCableOnlyNote")}
          </p>
        </div>

        {wiredDisplayMode === "dual_screen" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "16px" }} className="olc-anim-in">
            <DisplayLinkCard href="/grid" icon="touch_app" primary title={t("settingsPage.wiredDisplayOpenGrid")} description={t("settingsPage.wiredDisplayOpenGridDesc")} />
            <DisplayLinkCard href="/cinema" icon="tv" primary={false} title={t("settingsPage.wiredDisplayOpenCinema")} description={t("settingsPage.wiredDisplayOpenCinemaDesc")} />
          </div>
        )}

        <LidSetting showToast={showToast} />

        {data?.deployment_profile === "android" && (
          <p className="settings-hint" style={{ marginTop: "12px" }}>
            {t("settingsPage.wiredDisplayTabletHint")}
          </p>
        )}
      </div>
    </section>
  );
}
