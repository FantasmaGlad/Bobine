"use client";
import React from "react";
import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";

export default function UnlockOverlay({ t, onUnlock }: { t: (key: string, vars?: Record<string, string | number>) => string; onUnlock: () => void }) {
  return (
        <div className="radio-unlock-overlay">
          <AppLogo className="radio-unlock-logo" />
          <div>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, marginBottom: "8px" }}>{t("radioScreen.unlockTitle")}</div>
            <div style={{ color: "var(--text-muted)" }}>{t("radioScreen.unlockHint")}</div>
          </div>
          <button className="radio-unlock-btn" onClick={onUnlock}>
            <Icon name="play_circle" size={22} filled />
            {t("radioScreen.unlockButton")}
          </button>
        </div>
  );
}
