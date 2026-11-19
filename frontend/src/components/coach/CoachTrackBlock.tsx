"use client";

import { formatTime } from "@/lib/format";

export default function CoachTrackBlock({ label, title, remaining, audioProgress, accent }: {
  label: string; title: string | undefined; remaining: number | null; audioProgress: number; accent: string;
}) {
  return (
    <div className="coach-live-track-block olc-anim-in" style={{ width: "100%", maxWidth: "420px" }}>
      <span className="coach-live-track-label">
        {label}
      </span>
      <span className="coach-live-track-title">{title}</span>
      <span className="coach-live-track-time">- {formatTime(remaining)}</span>
      <div style={{ width: "100%", height: "6px", background: "var(--bg-surface-elevated)", borderRadius: "3px", overflow: "hidden", marginTop: "10px" }}>
        <div style={{ width: `${audioProgress}%`, height: "100%", background: accent, transition: "width 0.25s linear" }} />
      </div>
    </div>
  );
}
