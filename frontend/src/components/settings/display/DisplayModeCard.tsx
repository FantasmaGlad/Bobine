"use client";

import React from "react";
import Icon from "@/components/Icon";

interface DisplayModeCardProps {
  active: boolean;
  icon: string;
  title: string;
  description: string;
  detail?: string;
  onSelect: () => void;
}

const CARD: React.CSSProperties = { display: "flex", flexDirection: "column", alignItems: "flex-start", padding: "16px", textAlign: "left", height: "auto", gap: "8px" };

export default function DisplayModeCard({ active, icon, title, description, detail, onSelect }: DisplayModeCardProps) {
  return (
    <button type="button" className={`theme-picker-card ${active ? "active" : ""}`} style={CARD} onClick={onSelect}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", width: "100%" }}>
        <div style={{
          width: "36px",
          height: "36px",
          borderRadius: "var(--radius-sm)",
          background: active ? "var(--accent-primary)" : "var(--bg-surface-hover)",
          color: active ? "var(--accent-primary-fg)" : "var(--text-main)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}>
          <Icon name={icon} size={20} />
        </div>
        <div style={{ flex: 1 }}>
          <strong style={{ display: "block", fontSize: "0.95rem" }}>{title}</strong>
        </div>
        {active && (
          <span style={{ color: "var(--accent-text)", display: "flex", alignItems: "center" }}>
            <Icon name="check_circle" size={18} />
          </span>
        )}
      </div>
      <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>{description}</p>
      {detail !== undefined && <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--accent-text)", lineHeight: 1.4 }}>{detail}</p>}
    </button>
  );
}
