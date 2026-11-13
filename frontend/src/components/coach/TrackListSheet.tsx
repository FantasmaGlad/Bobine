"use client";
import React from "react";
import { formatTime } from "@/lib/format";

interface TrackListSheetProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  tracks: { id: number; title: string; duration_seconds: number | null }[];
  trackIndex: number;
  onJump: (index: number) => void;
  onClose: () => void;
}

export default function TrackListSheet({ t, tracks, trackIndex, onJump, onClose }: TrackListSheetProps) {
  return (
        <div className="coach-sheet-overlay" onClick={onClose}>
          <div className="coach-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="coach-sheet-handle" />
            <h3 style={{ margin: "0 0 12px" }}>{t("coach.courseTracksTitle")}</h3>
            <div className="coach-sheet-list">
              {tracks.map((track, idx) => (
                <button
                  key={track.id}
                  className={`coach-sheet-track olc-press ${idx === trackIndex ? "active" : ""}`}
                  onClick={() => onJump(idx)}
                >
                  <span>{idx + 1}. {track.title}</span>
                  <span style={{ color: "var(--text-muted)" }}>{formatTime(track.duration_seconds)}</span>
                </button>
              ))}
            </div>
            <button className="btn btn-secondary" style={{ height: "48px", marginTop: "12px" }} onClick={onClose}>
              {t("coach.close")}
            </button>
          </div>
        </div>
  );
}
