"use client";

import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { BackgroundItem } from "./types";

export default function CardFooter({ bg, onDelete }: { bg: BackgroundItem; onDelete: () => void }) {
  const { t } = useAppSettings();
  return (
    <div className="card-content" style={{ padding: "12px 6px 6px" }}>
      <h4 className="card-title" title={bg.title} style={{ fontSize: "0.95rem", fontWeight: 700, margin: "0 0 6px" }}>
        {bg.title}
      </h4>
      <div className="card-meta-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="release-badge" style={{ fontSize: "0.75rem" }}>
          {bg.is_image ? t("backgrounds.kindImage") : t("backgrounds.kindVideo")}
        </span>
        <button
          type="button"
          className="btn btn-danger"
          style={{ height: "30px", padding: "0 8px", fontSize: "0.75rem", display: "inline-flex", alignItems: "center", gap: "4px" }}
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          title={t("common.delete")}
        >
          <Icon name="delete" size={15} />
          {t("common.delete")}
        </button>
      </div>
    </div>
  );
}
