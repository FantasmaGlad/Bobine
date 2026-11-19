"use client";

import React from "react";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { formatMediaDuration } from "@/lib/format";
import type { BackgroundSummary, PlaylistDraftItem } from "./types";

export default function SequencerTrackInfo({ t, item, backgrounds, onBackground }: {
  t: (key: string) => string; item: PlaylistDraftItem; backgrounds: BackgroundSummary[]; onBackground: (backgroundId: number | null) => void;
}) {
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--text-main)", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
        {item.track.title}
      </div>
      <div style={{ display: "flex", gap: "6px", alignItems: "center", marginTop: "1px" }}>
        {item.track.course_program && (
          <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
            {item.track.course_program}
          </span>
        )}
        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
          {item.track.course_title} · {formatMediaDuration(item.track.duration_seconds)}
        </span>
      </div>
      <div onClick={(e) => e.stopPropagation()}>
        <ResponsiveSelect
          value={item.backgroundId != null ? String(item.backgroundId) : ""}
          onChange={(value) => onBackground(value ? Number(value) : null)}
          placeholder={t("audioPlaylists.trackBackgroundNone")}
          title={t("audioPlaylists.trackBackgroundLabel")}
          style={{ minHeight: "22px", fontSize: "0.68rem", padding: "0 4px", marginTop: "3px", maxWidth: "180px" }}
          options={backgrounds.map((bg) => ({ value: String(bg.id), label: bg.title }))}
        />
      </div>
    </div>
  );
}
