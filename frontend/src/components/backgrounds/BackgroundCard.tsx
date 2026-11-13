"use client";
import React, { useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
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
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (hovering && !bg.is_image) {
      video.currentTime = 0;
      video.play().catch(() => {});
    } else {
      video.pause();
    }
  }, [hovering, bg.is_image]);

  const thumbSrc = bg.thumbnail_path
    ? getApiUrl(`/thumbnails/${bg.thumbnail_path.split("/").pop()}`)
    : null;

  return (
    <div
      className={`video-card olc-press ${isActiveCable || isActiveNetwork ? "program-rpm" : ""}`}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      onClick={onClick}
      style={{ cursor: "pointer", position: "relative" }}
    >
      <div className="thumbnail-wrapper" style={{ position: "relative", aspectRatio: "16/9", overflow: "hidden", borderRadius: "10px" }}>
        {hovering && !bg.is_image ? (
          <video
            ref={videoRef}
            className="card-thumbnail"
            src={getApiUrl(`/backgrounds/${bg.id}/stream`)}
            muted
            loop
            playsInline
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : thumbSrc ? (
          <img
            src={thumbSrc}
            alt={bg.title}
            className="card-thumbnail"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "var(--bg-surface-elevated)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon name={bg.is_image ? "image" : "gradient"} size={32} style={{ opacity: 0.3 }} />
          </div>
        )}

        <div style={{ position: "absolute", top: 8, left: 8, display: "flex", flexDirection: "column", gap: "6px", zIndex: 3 }}>
          {isDefault && (
            <span
              style={{
                background: "var(--accent-primary)",
                color: "var(--accent-primary-fg)",
                padding: "3px 8px",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                boxShadow: "0 2px 8px color-mix(in srgb, var(--ink) 40%, transparent)",
              }}
            >
              <Icon name="bookmark" size={13} filled />
              {t("backgrounds.defaultBadge")}
            </span>
          )}
        </div>

        <div style={{ position: "absolute", top: 8, right: 8, display: "flex", flexDirection: "column", gap: "6px", alignItems: "flex-end", zIndex: 3 }}>
          {isActiveCable && (
            <span
              style={{
                background: "var(--accent-success)",
                color: "var(--ink)",
                padding: "3px 8px",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                boxShadow: "0 2px 8px color-mix(in srgb, var(--ink) 40%, transparent)",
              }}
            >
              <Icon name="cable" size={13} />
              {t("backgrounds.onCable")}
            </span>
          )}
          {isActiveNetwork && (
            <span
              style={{
                background: "var(--accent-primary)",
                color: "var(--accent-primary-fg)",
                padding: "3px 8px",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                boxShadow: "0 2px 8px color-mix(in srgb, var(--ink) 40%, transparent)",
              }}
            >
              <Icon name="wifi" size={13} />
              {t("backgrounds.onNetwork")}
            </span>
          )}
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

      <div className="card-content" style={{ padding: "12px 6px 6px" }}>
        <h4 className="card-title" title={bg.title} style={{ fontSize: "0.95rem", fontWeight: 700, margin: "0 0 6px" }}>
          {bg.title}
        </h4>
        <div className="card-meta-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="release-badge" style={{ fontSize: "0.75rem" }}>
            {bg.is_image ? t("backgrounds.kindImage") : t("backgrounds.kindVideo")}
          </span>
          <button
            type="button"
            className="btn btn-danger"
            style={{ height: "30px", padding: "0 8px", fontSize: "0.75rem", display: "inline-flex", alignItems: "center", gap: "4px" }}
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            title={t("common.delete")}
          >
            <Icon name="delete" size={15} />
            {t("common.delete")}
          </button>
        </div>
      </div>
    </div>
  );
}
