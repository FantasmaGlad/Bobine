"use client";

import Icon from "@/components/Icon";
import type { BackgroundItem } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export default function InspectorActions({ t, bg, isDefault, onToggleDefault, onBroadcastCable, onBroadcastNetwork, onDelete }: {
  t: Translate;
  bg: BackgroundItem;
  isDefault: boolean;
  onToggleDefault: (id: number) => void;
  onBroadcastCable: (bg: BackgroundItem) => void;
  onBroadcastNetwork: (bg: BackgroundItem) => void;
  onDelete: (bg: BackgroundItem) => void;
}) {
  return (
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
  );
}
