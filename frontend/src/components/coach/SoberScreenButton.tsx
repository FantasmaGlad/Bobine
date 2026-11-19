"use client";

import Icon from "@/components/Icon";

export default function SoberScreenButton({ label, active, onChoose }: { label: string; active: boolean; onChoose: () => void }) {
  return (
    <button
      type="button"
      className={`olc-press ${active ? "active" : ""}`}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "8px",
        width: "100%",
        minHeight: "40px",
        borderRadius: "var(--radius-md)",
        background: active ? "color-mix(in srgb, var(--accent-primary) 15%, var(--bg-surface-elevated))" : "var(--bg-surface-elevated)",
        border: `1.5px solid ${active ? "var(--accent-text)" : "var(--border-color)"}`,
        color: active ? "var(--accent-text)" : "var(--text-main)",
        fontWeight: 700,
        fontSize: "0.82rem",
        cursor: "pointer",
      }}
      onClick={onChoose}
    >
      <Icon name="hide_image" size={18} />
      {label}
      {active && <Icon name="check_circle" size={16} filled />}
    </button>
  );
}
