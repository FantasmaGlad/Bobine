"use client";

import Icon from "@/components/Icon";

export default function CardBadge({ icon, label, background, color, filled = false }: {
  icon: string; label: string; background: string; color: string; filled?: boolean;
}) {
  return (
    <span
      style={{
        background,
        color,
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
      <Icon name={icon} size={13} filled={filled} />
      {label}
    </span>
  );
}
