"use client";
import React from "react";
import SequencerZone from "@/components/playlist-editor/SequencerZone";
import SequencerTrackInfo from "./SequencerTrackInfo";
import type { BackgroundSummary, PlaylistDraftItem, Sequencer } from "./types";

interface AudioSequencerProps {
  t: (key: string, vars?: Record<string, string | number>) => string;
  isMobile: boolean;
  playlistItems: PlaylistDraftItem[];
  backgrounds: BackgroundSummary[];
  sequencer: Sequencer;
  handleSetTrackBackground: (index: number, backgroundId: number | null) => void;
}

export default function AudioSequencer({ t, isMobile, playlistItems, backgrounds, sequencer, handleSetTrackBackground }: AudioSequencerProps) {
  return (
    <SequencerZone
      isMobile={isMobile} items={playlistItems} sequencer={sequencer}
      itemKey={(item, index) => `${item.track.id}-${index}`}
      renderInfo={(item, index) => <SequencerTrackInfo t={t} item={item} backgrounds={backgrounds} onBackground={(id) => handleSetTrackBackground(index, id)} />}
      empty={{ title: t("audioPlaylists.emptySequencer"), hint: t("audioPlaylists.emptySequencerHint") }}
      actionLabels={{ up: t("audioPlaylists.moveUp"), down: t("audioPlaylists.moveDown"), remove: t("audioPlaylists.remove") }}
      actionsStyle={{ display: "flex", gap: "4px", flexShrink: 0 }}
    />
  );
}
