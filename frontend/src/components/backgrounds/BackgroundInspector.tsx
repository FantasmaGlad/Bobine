"use client";
import React from "react";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import type { BackgroundItem } from "./types";
import InspectorActions from "./InspectorActions";
import InspectorFacts from "./InspectorFacts";
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

            <InspectorFacts t={t} bg={bg} isDefault={isDefault} />
            <InspectorActions t={t} bg={bg} isDefault={isDefault} onToggleDefault={onToggleDefault}
              onBroadcastCable={onBroadcastCable} onBroadcastNetwork={onBroadcastNetwork} onDelete={onDelete} />
          </div>
        </div>
  );
}
