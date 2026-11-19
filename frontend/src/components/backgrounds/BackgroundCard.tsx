"use client";
import React, { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import CardBadge from "./CardBadge";
import CardFooter from "./CardFooter";
import CardPreview from "./CardPreview";
import type { BackgroundItem } from "./types";

export default function BackgroundCard({
  bg,
  isDefault,
  isActiveCable,
  isActiveNetwork,
  onClick,
  onDelete,
}: {
  bg: BackgroundItem;
  isDefault: boolean;
  isActiveCable: boolean;
  isActiveNetwork: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  const { t } = useAppSettings();
  const [hovering, setHovering] = useState(false);

  return (
    <div
      className={`video-card olc-press ${isActiveCable || isActiveNetwork ? "program-rpm" : ""}`}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      onClick={onClick}
      style={{ cursor: "pointer", position: "relative" }}
    >
      <div className="thumbnail-wrapper" style={{ position: "relative", aspectRatio: "16/9", overflow: "hidden", borderRadius: "10px" }}>
        <CardPreview bg={bg} hovering={hovering} />

        <div style={{ position: "absolute", top: 8, left: 8, display: "flex", flexDirection: "column", gap: "6px", zIndex: 3 }}>
          {isDefault && (
            <CardBadge icon="bookmark" filled label={t("backgrounds.defaultBadge")} background="var(--accent-primary)" color="var(--accent-primary-fg)" />
          )}
        </div>

        <div style={{ position: "absolute", top: 8, right: 8, display: "flex", flexDirection: "column", gap: "6px", alignItems: "flex-end", zIndex: 3 }}>
          {isActiveCable && <CardBadge icon="cable" label={t("backgrounds.onCable")} background="var(--accent-success)" color="var(--ink)" />}
          {isActiveNetwork && <CardBadge icon="wifi" label={t("backgrounds.onNetwork")} background="var(--accent-primary)" color="var(--accent-primary-fg)" />}
        </div>

        <span
          className="card-duration"
          style={{
            position: "absolute",
            bottom: 8,
            right: 8,
            background: "color-mix(in srgb, var(--ink) 75%, transparent)",
            color: "var(--specular)",
            padding: "2px 6px",
            borderRadius: "4px",
            fontSize: "0.72rem",
            fontWeight: 600,
          }}
        >
          {bg.duration_seconds ? `${Math.round(bg.duration_seconds)}s` : t("backgrounds.infiniteLoop")}
        </span>
      </div>

      <CardFooter bg={bg} onDelete={onDelete} />
    </div>
  );
}
