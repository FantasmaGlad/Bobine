"use client";
import React from "react";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { ShowToast } from "@/lib/useToast";
import ActiveLogoPicker from "./branding/ActiveLogoPicker";
import LogoActions from "./branding/LogoActions";
import { useLogo } from "./branding/useLogo";

export default function BrandingSection({ hidden, showToast }: { hidden: boolean; showToast: ShowToast }) {
  const { t, hasCustomLogo } = useAppSettings();
  const logo = useLogo(showToast);

  return (
      <section className="live-block" id="section-branding" hidden={hidden}>
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
            {hasCustomLogo && <ActiveLogoPicker />}
            <LogoActions {...logo} />
            <p className="settings-hint" style={{ margin: 0 }}>
              {t("settingsPage.logoHint")}
            </p>
          </div>
        </div>
      </section>
  );
}
