"use client";
import React from "react";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import type { BackgroundItem } from "./types";

interface BackgroundInspectorProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  bg: BackgroundItem;
  isDefault: boolean;
  onClose: () => void;
  onToggleDefault: (id: number) => void;
  onBroadcastCable: (bg: BackgroundItem) => void;
  onBroadcastNetwork: (bg: BackgroundItem) => void;
  onDelete: (bg: BackgroundItem) => void;
}

export default function BackgroundInspector({ t, bg, isDefault, onClose, onToggleDefault, onBroadcastCable, onBroadcastNetwork, onDelete }: BackgroundInspectorProps) {
  return (
        <div className="modal-overlay" onClick={onClose}>
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "640px", width: "100%", padding: "24px" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Icon name={bg.is_image ? "image" : "videocam"} size={22} color="var(--accent-text)" />
                <h3 style={{ fontSize: "1.2rem", fontWeight: 800, margin: 0 }}>
                  {bg.title}
                </h3>
              </div>
              <button aria-label={t("common.close")}
                className="coach-icon-btn olc-press"
                style={{ width: "36px", height: "36px", fontSize: "0.9rem" }}
                onClick={onClose}
              >
                <Icon name="close" size={18} />
              </button>
            </div>

            <div style={{ position: "relative", width: "100%", aspectRatio: "16/9", borderRadius: "10px", overflow: "hidden", background: "var(--ink)", marginBottom: "16px" }}>
              {bg.is_image ? (
                <img
                  src={getApiUrl(`/backgrounds/${bg.id}/stream`)}
                  alt={bg.title}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <video
                  src={getApiUrl(`/backgrounds/${bg.id}/stream`)}
                  autoPlay
                  loop
                  muted
                  playsInline
                  controls
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              )}
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: "10px",
                padding: "12px",
                background: "var(--bg-surface-elevated)",
                borderRadius: "8px",
                marginBottom: "20px",
                fontSize: "0.85rem",
              }}
            >
              <div>
                <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.75rem" }}>{t("backgrounds.formatLabel")}</span>
                <strong style={{ color: "var(--text-main)" }}>{bg.is_image ? t("backgrounds.stillImage") : t("backgrounds.videoLoop")}</strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.75rem" }}>{t("backgrounds.durationLabel")}</span>
                <strong style={{ color: "var(--text-main)" }}>
                  {bg.duration_seconds ? `${Math.round(bg.duration_seconds)}s` : t("backgrounds.infiniteLoop")}
                </strong>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.75rem" }}>{t("common.coachMode")}</span>
                <strong style={{ color: isDefault ? "var(--accent-text)" : "var(--text-muted)" }}>
                  {isDefault ? t("backgrounds.isDefault") : t("backgrounds.isOptional")}
                </strong>
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  type="button"
                  className={`btn ${isDefault ? "btn-secondary" : "btn-primary"}`}
                  style={{ flex: 1, height: "44px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                  onClick={() => onToggleDefault(bg.id)}
                >
                  <Icon name={isDefault ? "bookmark_remove" : "bookmark_add"} size={18} />
                  {isDefault ? t("backgrounds.unsetDefaultCoach") : t("backgrounds.setAsDefaultCoach")}
                </button>
              </div>

              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ flex: 1, minWidth: "200px", height: "44px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                  onClick={() => onBroadcastCable(bg)}
                >
                  <Icon name="cable" size={18} color="var(--accent-success-text)" />
                  {t("backgrounds.broadcastCable")}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ flex: 1, minWidth: "200px", height: "44px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
                  onClick={() => onBroadcastNetwork(bg)}
                >
                  <Icon name="wifi" size={18} color="var(--accent-text)" />
                  {t("backgrounds.broadcastNetwork")}
                </button>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
                <button
                  type="button"
                  className="btn btn-danger"
                  style={{ height: "38px", display: "inline-flex", alignItems: "center", gap: "6px" }}
                  onClick={() => onDelete(bg)}
                >
                  <Icon name="delete" size={16} />
                  {t("common.delete")}
                </button>
              </div>
            </div>
          </div>
        </div>
  );
}
