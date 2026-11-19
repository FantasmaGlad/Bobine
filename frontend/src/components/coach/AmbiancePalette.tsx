"use client";
import React from "react";
import type { BackgroundSummary } from "./types";import AmbianceThumb from "./AmbianceThumb";
import SoberScreenButton from "./SoberScreenButton";

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

            <SoberScreenButton label={t("coach.soberScreenBtn")} active={!activeBgId} onChoose={() => chooseBackground(null)} />

            <div className="coach-ambiance-grid">
              {backgrounds.map((bg) => (
                <AmbianceThumb key={bg.id} t={t} bg={bg} isActive={activeBgId === bg.id} onChoose={() => chooseBackground(bg.id)} />
              ))}
            </div>
          </div>
  );
}
