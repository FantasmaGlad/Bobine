"use client";

import React from "react";
import { channelI18nSuffix, channelLogoUrl, RELEASE_CHANNELS, type UpdateChannel } from "@/lib/releaseChannel";

interface ChannelPickerProps {
  t: (key: string) => string;
  current: string;
  disabled: boolean;
  onPick: (channel: UpdateChannel) => void;
}

export default function ChannelPicker({ t, current, disabled, onPick }: ChannelPickerProps) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", maxWidth: "520px", gap: "16px", flexWrap: "wrap" }}>
      <span className="form-label" style={{ margin: 0, fontWeight: 600 }}>
        {t("settingsPage.updateChannelLabel")}
      </span>
      <div
        style={{
          display: "inline-flex",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
          border: "1px solid var(--border-color)",
          background: "var(--bg-surface-elevated)",
        }}
      >
        {RELEASE_CHANNELS.map((channel) => (
          <button
            key={channel}
            type="button"
            className={`btn btn-sm ${current === channel ? "btn-primary" : "btn-secondary"}`}
            style={{ borderRadius: 0, border: "none", minHeight: "34px", padding: "6px 14px", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: "6px" }}
            onClick={() => onPick(channel)}
            disabled={disabled}
          >
            <img src={channelLogoUrl(channel)} alt="" width={18} height={18} style={{ borderRadius: "4px" }} />
            {t(`settingsPage.updateChannel${channelI18nSuffix(channel)}`)}
          </button>
        ))}
      </div>
    </div>
  );
}
