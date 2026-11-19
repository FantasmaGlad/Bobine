"use client";

import Icon from "@/components/Icon";

export default function ActiveBackgroundBanner({ accent, labelColor, icon, label, title, stopLabel, onStop }: {
  accent: string; labelColor: string; icon: string; label: string; title: string | undefined; stopLabel: string; onStop: () => void;
}) {
  return (
    <div
      className="interrupted-block"
      style={{ borderColor: `color-mix(in srgb, ${accent} 40%, transparent)`, margin: 0 }}
    >
      <div className="interrupted-text">
        <span className="interrupted-label" style={{ color: labelColor, display: "flex", alignItems: "center", gap: "6px" }}>
          <Icon name={icon} size={16} />
          {label}
        </span>
        <span className="interrupted-title">{title}</span>
      </div>
      <button className="btn btn-secondary" onClick={onStop}>
        {stopLabel}
      </button>
    </div>
  );
}
