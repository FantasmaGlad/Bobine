"use client";

import React from "react";
import Icon from "@/components/Icon";

interface DisplayLinkCardProps {
  href: string;
  icon: string;
  primary: boolean;
  title: string;
  description: string;
}

const LINK: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "16px 20px",
  borderRadius: "var(--radius-md)",
  background: "var(--bg-surface-elevated)",
  border: "1px solid var(--border-color)",
  textDecoration: "none",
  color: "inherit",
  gap: "16px",
};

export default function DisplayLinkCard({ href, icon, primary, title, description }: DisplayLinkCardProps) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="wired-display-action-card olc-card-hover" style={LINK}>
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        <div style={{
          width: "42px",
          height: "42px",
          borderRadius: "var(--radius-sm)",
          background: primary ? "var(--accent-primary)" : "var(--bg-surface-hover)",
          color: primary ? "var(--accent-primary-fg)" : "var(--text-main)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}>
          <Icon name={icon} size={22} />
        </div>
        <div>
          <strong style={{ display: "block", fontSize: "0.98rem", color: "var(--text-main)", marginBottom: "3px" }}>{title}</strong>
          <span style={{ fontSize: "0.84rem", color: "var(--text-muted)", lineHeight: 1.4 }}>{description}</span>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--accent-text)", fontWeight: 700, fontSize: "0.9rem", flexShrink: 0 }}>
        <span>{title}</span>
        <Icon name="open_in_new" size={16} />
      </div>
    </a>
  );
}
