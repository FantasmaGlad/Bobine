"use client";

import Icon from "@/components/Icon";
import type { PlaybackState } from "@/lib/usePlaybackSocket";

type Translate = (key: string, vars?: Record<string, string | number>) => string;
type Send = (command: string, params?: Record<string, unknown>) => unknown;

export default function CoachSettingsRows({ t, state, sendCommand }: { t: Translate; state: PlaybackState; sendCommand: Send }) {
  const CHAIN_MODE_LABELS: Record<string, string> = {
    auto: t("coach.chainModeLabels.auto"),
    manual: t("coach.chainModeLabels.manual"),
  };
  return (
    <>
      <div className="coach-volume-row">
        <button aria-label={t("common.volumeDown")} className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.max(0, state.volume - 10) })}>
          <Icon name="remove" size={18} />
        </button>
        <span className="coach-volume-value">
          <Icon name="volume_up" size={16} style={{ marginRight: "4px" }} />
          {state.volume}%
        </span>
        <button aria-label={t("common.volumeUp")} className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.min(100, state.volume + 10) })}>
          <Icon name="add" size={18} />
        </button>
      </div>

      <div className="coach-chain-mode-row">
        {(["auto", "manual"] as const).map((mode) => (
          <button
            key={mode}
            className={`speed-btn ${state.audio_chain_mode === mode ? "active" : ""}`}
            style={{ minHeight: "44px", flex: 1 }}
            onClick={() => sendCommand("audio_set_chain_mode", { mode })}
          >
            {CHAIN_MODE_LABELS[mode]}
          </button>
        ))}
      </div>
    </>
  );
}
