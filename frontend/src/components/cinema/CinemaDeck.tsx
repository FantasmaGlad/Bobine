"use client";

import React from "react";

import { getApiUrl } from "@/lib/apiUrl";
import { subtitleSrc, type SubtitleTrack } from "@/lib/subtitles";

interface Props {
  deck: "a" | "b";
  active: boolean;
  ref: React.Ref<HTMLVideoElement>;
  subtitles: SubtitleTrack[];
  onPosition: (seconds: number) => void;
  onEnded: () => void;
  onPlaying: (playing: boolean) => void;
  onSeeked: (seconds: number) => void;
  onClick: () => void;
}

export default function CinemaDeck({ deck, active, ref, subtitles, onPosition, onEnded, onPlaying, onSeeked, onClick }: Props) {
  return (
    <video
      ref={ref}
      className={`cinema-deck cinema-deck-${deck} ${active ? "deck-active" : "deck-idle"}`}
      preload="auto"
      crossOrigin="anonymous"
      onTimeUpdate={(e) => { if (active && !e.currentTarget.seeking) onPosition(e.currentTarget.currentTime); }}
      onEnded={() => { if (active) onEnded(); }}
      onPlay={() => { if (active) onPlaying(true); }}
      onPause={() => { if (active) onPlaying(false); }}
      onSeeked={(e) => { if (active) onSeeked(e.currentTarget.currentTime); }}
      onClick={onClick}
      playsInline
    >
      {subtitles.map((sub) => (
        <track key={sub.id} kind="subtitles" data-subtitle-id={sub.id} src={subtitleSrc(getApiUrl, sub.vtt_url)} srcLang={sub.language_code} label={sub.language_label} />
      ))}
    </video>
  );
}
