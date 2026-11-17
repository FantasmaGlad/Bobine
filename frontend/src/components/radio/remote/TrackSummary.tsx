"use client";

import React from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { RadioTrackInfo } from "@/lib/useRadioSocket";

const COVER: React.CSSProperties = {
  width: "104px",
  height: "104px",
  borderRadius: "var(--radius-md)",
  flexShrink: 0,
  background: "var(--bg-surface-elevated)",
  border: "1px solid var(--border-color)",
};

export default function TrackSummary({ track, coverSrc }: { track: RadioTrackInfo; coverSrc: string | null }) {
  const { t } = useAppSettings();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "18px", flexWrap: "wrap" }}>
      {coverSrc ? (
        <img
          src={coverSrc}
          alt=""
          style={{ ...COVER, objectFit: "cover", boxShadow: "0 8px 24px color-mix(in srgb, var(--ink) 35%, transparent)" }}
        />
      ) : (
        <div style={{ ...COVER, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon name="music_note" size={44} style={{ opacity: 0.3 }} />
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="live-title" style={{ fontSize: "1.35rem", marginBottom: "4px" }}>
          {track.title}
        </div>
        <div style={{ fontSize: "0.95rem", color: "var(--text-muted)", fontWeight: 600 }}>
          {track.artist || t("radioLibrary.unknownArtist")}
          {track.album ? ` — ${track.album}` : ""}
        </div>
      </div>
    </div>
  );
}
