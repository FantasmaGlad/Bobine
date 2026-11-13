"use client";
import React from "react";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import type { BackgroundSummary } from "./types";

interface AmbiancePaletteProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  backgrounds: BackgroundSummary[];
  activeBgId: number | null;
  chooseBackground: (id: number | null) => void;
}

export default function AmbiancePalette({ t, backgrounds, activeBgId, chooseBackground }: AmbiancePaletteProps) {
  return (
          <div className="coach-ambiance-panel">
            <div className="coach-ambiance-header">
              <div>
                <h3 style={{ fontSize: "1rem", fontWeight: 800, margin: 0 }}>
                  {t("coach.ambiancePaletteTitle")}
                </h3>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  {t("coach.stageMonitorHint")}
                </span>
              </div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 600 }}>
                {t("coach.ambianceCount", { count: backgrounds.length })}
              </span>
            </div>

            <button
              type="button"
              className={`olc-press ${!activeBgId ? "active" : ""}`}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                width: "100%",
                minHeight: "40px",
                borderRadius: "var(--radius-md)",
                background: !activeBgId ? "color-mix(in srgb, var(--accent-primary) 15%, var(--bg-surface-elevated))" : "var(--bg-surface-elevated)",
                border: `1.5px solid ${!activeBgId ? "var(--accent-text)" : "var(--border-color)"}`,
                color: !activeBgId ? "var(--accent-text)" : "var(--text-main)",
                fontWeight: 700,
                fontSize: "0.82rem",
                cursor: "pointer",
              }}
              onClick={() => chooseBackground(null)}
            >
              <Icon name="hide_image" size={18} />
              {t("coach.soberScreenBtn")}
              {!activeBgId && <Icon name="check_circle" size={16} filled />}
            </button>

            <div className="coach-ambiance-grid">
              {backgrounds.map((bg) => {
                const isActive = activeBgId === bg.id;
                const thumb = bg.thumbnail_path
                  ? getApiUrl(`/thumbnails/${bg.thumbnail_path.split("/").pop()}`)
                  : null;
                return (
                  <div
                    key={bg.id}
                    className={`coach-ambiance-thumb-card olc-press ${isActive ? "active" : ""}`}
                    onClick={() => chooseBackground(bg.id)}
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
                        {bg.is_image ? "Image" : bg.duration_seconds ? `${Math.round(bg.duration_seconds)}s` : "Boucle"}
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
              })}
            </div>
          </div>
  );
}
