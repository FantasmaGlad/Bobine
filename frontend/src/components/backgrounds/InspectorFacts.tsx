"use client";

import type { BackgroundItem } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

function Fact({ label, value, color = "var(--text-main)" }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.75rem" }}>{label}</span>
      <strong style={{ color }}>{value}</strong>
    </div>
  );
}

export default function InspectorFacts({ t, bg, isDefault }: { t: Translate; bg: BackgroundItem; isDefault: boolean }) {
  return (
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
      <Fact label={t("backgrounds.formatLabel")} value={bg.is_image ? t("backgrounds.stillImage") : t("backgrounds.videoLoop")} />
      <Fact label={t("backgrounds.durationLabel")} value={bg.duration_seconds ? `${Math.round(bg.duration_seconds)}s` : t("backgrounds.infiniteLoop")} />
      <Fact label={t("common.coachMode")} value={isDefault ? t("backgrounds.isDefault") : t("backgrounds.isOptional")}
        color={isDefault ? "var(--accent-text)" : "var(--text-muted)"} />
    </div>
  );
}
