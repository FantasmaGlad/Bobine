"use client";
import React from "react";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import { formatTime } from "@/lib/format";

interface CoachStageMonitorProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  activeBgId: number | null;
  activeBgIsImage: boolean;
  activeBgTitle: string | null | undefined;
  title: string | undefined;
  trackLabel: string;
  localPos: number;
  duration: number | null | undefined;
  audioProgress: number;
  accent: string;
}

export default function CoachStageMonitor({
  t, activeBgId, activeBgIsImage, activeBgTitle, title, trackLabel, localPos, duration, audioProgress, accent,
}: CoachStageMonitorProps) {
  return (
          <div className="coach-stage-monitor">
            {activeBgId ? (
              activeBgIsImage ? (
                <img
                  className="coach-monitor-media"
                  src={getApiUrl(`/backgrounds/${activeBgId}/stream`)}
                  alt=""
                />
              ) : (
                <video
                  className="coach-monitor-media"
                  src={getApiUrl(`/backgrounds/${activeBgId}/stream`)}
                  autoPlay
                  loop
                  muted
                  playsInline
                />
              )
            ) : (
              <div className="coach-monitor-placeholder">
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", opacity: 0.35 }}>
                  <Icon name="hide_image" size={36} color="var(--accent-text)" />
                  <span style={{ fontSize: "0.8rem", fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    {t("coach.soberScreenActive")}
                  </span>
                </div>
              </div>
            )}

            <div className="coach-monitor-gradient" />

            <div className="coach-monitor-top">
              <span className="coach-monitor-badge">
                <span className="coach-monitor-live-dot" />
                {t("coach.stageMonitorTitle")}
              </span>
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  padding: "3px 8px",
                  borderRadius: "12px",
                  background: "color-mix(in srgb, var(--ink) 60%, transparent)",
                  color: "color-mix(in srgb, var(--specular) 90%, transparent)",
                  backdropFilter: "blur(var(--blur-sm))",
                  border: "1px solid color-mix(in srgb, var(--specular) 15%, transparent)",
                }}
              >
                {activeBgTitle || t("coach.soberScreenActive")}
              </span>
            </div>

            <div className="coach-monitor-bottom">
              <h2 className="coach-monitor-track-title">
                {title}
              </h2>
              <div className="coach-monitor-meta">
                <span>{trackLabel}</span>
                <span>
                  {formatTime(localPos)} / {formatTime(duration)}
                </span>
              </div>
              <div style={{ width: "100%", height: "4px", background: "color-mix(in srgb, var(--specular) 20%, transparent)", borderRadius: "2px", overflow: "hidden" }}>
                <div style={{ width: `${audioProgress}%`, height: "100%", background: accent, transition: "width 0.25s linear" }} />
              </div>
            </div>
          </div>
  );
}
