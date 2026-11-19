"use client";

import Icon from "@/components/Icon";
import type { useToast } from "@/lib/useToast";

type Toast = NonNullable<ReturnType<typeof useToast>["toast"]>;

export default function SettingsToast({ toast }: { toast: Toast }) {
  return (
    <div
      className={`toast ${toast.type} ${toast.onClick ? "clickable olc-press" : ""}`}
      onClick={toast.onClick}
      style={{ cursor: toast.onClick ? "pointer" : "default" }}
      role={toast.onClick ? "button" : undefined}
      tabIndex={toast.onClick ? 0 : undefined}
    >
      {toast.type === "warning" && <Icon name="system_update" size={18} color="var(--accent-text)" />}
      <span>{toast.message}</span>
      {toast.onClick && <Icon name="arrow_downward" size={16} />}
    </div>
  );
}
