"use client";

import Icon from "@/components/Icon";
import { thumbnailUrl } from "@/lib/thumbnail";
import type { BackgroundSummary } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export default function AmbianceThumb({ t, bg, isActive, onChoose }: { t: Translate; bg: BackgroundSummary; isActive: boolean; onChoose: () => void }) {
  const thumb = thumbnailUrl(bg.thumbnail_path);
  return (
        <div
          className={`coach-ambiance-thumb-card olc-press ${isActive ? "active" : ""}`}
          onClick={onChoose}
          title={bg.title}
        >
          <div className="coach-ambiance-thumb-media">
            {thumb ? (
              <img src={thumb} alt={bg.title} />
            ) : (
              <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Icon name={bg.is_image ? "image" : "videocam"} size={22} style={{ opacity: 0.4 }} />
              </div>
            )}
            {isActive && (
              <span
                style={{
                  position: "absolute",
                  top: 4,
                  right: 4,
                  background: "var(--accent-primary)",
                  color: "var(--accent-primary-fg)",
                  borderRadius: "4px",
                  padding: "1px 5px",
                  fontSize: "0.68rem",
                  fontWeight: 800,
                  boxShadow: "0 2px 6px color-mix(in srgb, var(--ink) 50%, transparent)",
                }}
              >
                {t("common.active")}
              </span>
            )}
            <span
              style={{
                position: "absolute",
                bottom: 3,
                right: 3,
                background: "color-mix(in srgb, var(--ink) 70%, transparent)",
                color: "var(--specular)",
                borderRadius: "3px",
                padding: "1px 4px",
                fontSize: "0.65rem",
                fontWeight: 600,
              }}
            >
              {bg.is_image ? t("common.image") : bg.duration_seconds ? `${Math.round(bg.duration_seconds)}s` : t("common.loop")}
            </span>
          </div>
          <div
            style={{
              padding: "6px 8px",
              fontSize: "0.78rem",
              fontWeight: 600,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              color: isActive ? "var(--accent-text)" : "var(--text-main)",
            }}
          >
            {bg.title}
          </div>
        </div>
  );
}
