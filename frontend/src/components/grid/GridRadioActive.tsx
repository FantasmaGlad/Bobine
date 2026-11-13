"use client";
import React from "react";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import { formatWallClock } from "@/lib/format";

export default function GridRadioActive({ t, now }: { t: (key: string, vars?: Record<string, string | number>) => string; now: Date }) {
  return (
      <div className="grid-standby-root" style={{ overflowY: "auto", alignItems: "flex-start" }}>
        <div className="dashboard-container" style={{ width: "100%", maxWidth: "920px", margin: "0 auto", padding: "20px" }}>
          <div className="live-block" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
            <AppLogo size={40} className="grid-standby-logo" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <h3 style={{ margin: 0 }}>
                <Icon name="radio" size={18} /> {t("radioRemote.gridRadioActiveTitle")}
              </h3>
              <p style={{ margin: "4px 0 0", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                {t("radioRemote.gridRadioActiveHint")}
              </p>
            </div>
            <span className="grid-standby-clock">{formatWallClock(now)}</span>
          </div>
          <RadioRemotePanel key="radio_cable" channel="radio_cable" variant="compact" />
        </div>
      </div>
  );
}
