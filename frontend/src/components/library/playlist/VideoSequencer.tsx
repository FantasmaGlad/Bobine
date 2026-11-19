"use client";
import React from "react";
import SequencerZone from "@/components/playlist-editor/SequencerZone";
import { formatItemDuration, type Sequencer, type Video } from "./types";

interface VideoSequencerProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  isMobile: boolean;
  playlistItems: Video[];
  sequencer: Sequencer;
}

function VideoInfo({ t, item }: { t: VideoSequencerProps["t"]; item: Video }) {
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--text-main)", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
        {item.title}
      </div>
      <div style={{ display: "flex", gap: "6px", alignItems: "center", marginTop: "1px" }}>
        {item.program && (
          <span className="program-badge autre" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
            {item.program}
          </span>
        )}
        {item.release && (
          <span className="release-badge" style={{ fontSize: "0.55rem", padding: "1px 4px" }}>
            {t("playlists.releaseBadge", { release: item.release })}
          </span>
        )}
        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
          {formatItemDuration(item.duration_seconds)}
        </span>
      </div>
    </div>
  );
}

export default function VideoSequencer({ t, isMobile, playlistItems, sequencer }: VideoSequencerProps) {
  return (
    <SequencerZone
      isMobile={isMobile} items={playlistItems} sequencer={sequencer}
      itemKey={(item, index) => `${item.id}-${index}`}
      renderInfo={(item) => <VideoInfo t={t} item={item} />}
      empty={{ title: t("playlists.emptySequencer"), hint: t("playlists.emptySequencerHint") }}
      actionLabels={{ up: t("playlists.moveUp"), down: t("playlists.moveDown"), remove: t("playlists.remove") }}
      actionsStyle={{ display: "flex", gap: "4px" }}
    />
  );
}
