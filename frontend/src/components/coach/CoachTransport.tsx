"use client";

import Icon from "@/components/Icon";
import type { PlaybackState } from "@/lib/usePlaybackSocket";

type Translate = (key: string, vars?: Record<string, string | number>) => string;
type Send = (command: string, params?: Record<string, unknown>) => unknown;

export default function CoachTransport({ t, state, sendCommand, trackIndex, trackCount, accent, accentFg }: {
  t: Translate; state: PlaybackState; sendCommand: Send; trackIndex: number; trackCount: number; accent: string; accentFg: string;
}) {
  return (
    <>
      <div className="coach-controls-grid">
        <button className="coach-btn olc-press" onClick={() => sendCommand("audio_previous_track")} disabled={trackIndex <= 0} title={t("common.previous")}>
          <Icon name="skip_previous" size={28} filled />
        </button>
        <button
          className="coach-btn coach-btn-main olc-press"
          style={{ background: accent, color: accentFg }}
          onClick={() => sendCommand(state.audio_playing ? "pause" : "play")}
          title={state.audio_playing ? t("common.pause") : t("common.play")}
        >
          <Icon name={state.audio_playing ? "pause" : "play_arrow"} size={36} color={accentFg} filled />
        </button>
        <button
          className="coach-btn olc-press"
          onClick={() => sendCommand("audio_next_track")}
          disabled={trackIndex >= trackCount - 1}
          title={t("common.next")}
        >
          <Icon name="skip_next" size={28} filled />
        </button>
      </div>

      <button className="coach-btn coach-btn-wide olc-press" onClick={() => sendCommand("audio_restart_track")}>
        <Icon name="restart_alt" size={18} />
        {t("coach.restartTrack")}
      </button>
    </>
  );
}
