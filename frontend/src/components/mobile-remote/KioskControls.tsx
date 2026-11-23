"use client";

import React, { useRef, useState } from "react";
import Link from "next/link";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { PlaybackState } from "@/lib/usePlaybackSocket";
import { DEFAULT_OUTPUT, outputById, type OutputId } from "@/lib/outputs";

const STOP_HOLD_MS = 650;

interface KioskControlsProps {
  state: PlaybackState;
  isActive: boolean;
  channel?: OutputId;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
  onLaunch: () => void;
}

function useStopHold(sendCommand: KioskControlsProps["sendCommand"]) {
  const [holding, setHolding] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const start = (e: React.PointerEvent<HTMLButtonElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setHolding(true);
    timerRef.current = setTimeout(() => {
      sendCommand("stop");
      setHolding(false);
    }, STOP_HOLD_MS);
  };
  const cancel = () => {
    setHolding(false);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };
  return { holding, start, cancel };
}

export default function KioskControls({ state, isActive, channel, sendCommand, onLaunch }: KioskControlsProps) {
  const { t } = useAppSettings();
  const stop = useStopHold(sendCommand);
  const playable = isActive && state.state !== "background";
  return (
    <>
      <div className="mobile-remote-controls">
        <button aria-label={t("common.previous")} className="coach-btn olc-press" onClick={() => sendCommand("previous_video")} disabled={state.playlist_index === null || state.playlist_index === 0}>
          <Icon name="skip_previous" size={28} filled />
        </button>
        <button aria-label={state.state === "playing" ? t("common.pause") : t("common.play")}
          className="coach-btn coach-btn-main olc-press"
          style={playable ? { background: "var(--accent-primary)", color: "var(--accent-primary-fg)" } : undefined}
          onClick={() => sendCommand(state.state === "playing" ? "pause" : "play")}
          disabled={!playable}
        >
          <Icon name={state.state === "playing" ? "pause" : "play_arrow"} size={38} filled />
        </button>
        <button aria-label={t("common.next")} className="coach-btn olc-press" onClick={() => sendCommand("next_video")}
          disabled={state.playlist_items === null || state.playlist_index === (state.playlist_items?.length ?? 1) - 1}>
          <Icon name="skip_next" size={28} filled />
        </button>
      </div>

      <button
        className={`coach-btn coach-btn-wide mobile-remote-stop olc-press ${stop.holding ? "holding" : ""}`}
        style={{ touchAction: "none" }}
        disabled={!isActive}
        title={!isActive ? t("mobileRemote.noCourseHint") : undefined}
        onPointerDown={stop.start}
        onPointerUp={stop.cancel}
        onPointerCancel={stop.cancel}
        onContextMenu={(e) => e.preventDefault()}
      >
        <Icon name="stop_circle" size={18} />
        {stop.holding ? t("mobileRemote.holdToStop") : t("mobileRemote.stopHoldLabel")}
      </button>

      <div className="coach-volume-row" style={{ maxWidth: "none" }}>
        <button aria-label={t("common.volumeDown")} className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.max(0, state.volume - 10) })}>
          <Icon name="remove" size={20} />
        </button>
        <span className="coach-volume-value">
          <Icon name="volume_up" size={18} style={{ marginRight: "6px" }} />
          {state.volume}%
        </span>
        <button aria-label={t("common.volumeUp")} className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.min(100, state.volume + 10) })}>
          <Icon name="add" size={20} />
        </button>
      </div>

      <div className="mobile-remote-quick-row">
        {isActive && (
          <button className="btn btn-secondary mobile-remote-quick-btn" onClick={onLaunch}>
            <Icon name="play_circle" size={18} />
            {t("mobileRemote.launchQuickBtn")}
          </button>
        )}
        {outputById(channel ?? DEFAULT_OUTPUT).coach && (
          <Link href="/coach/" className="btn btn-primary mobile-remote-quick-btn" style={{ textDecoration: "none" }}>
            <Icon name="mic" size={18} />
            {t("mobileRemote.coachQuickBtn")}
          </Link>
        )}
      </div>

      <a href={`/schedule/?channel=${channel ?? DEFAULT_OUTPUT}`} className="btn btn-secondary" style={{ textDecoration: "none", width: "100%", minHeight: "50px", flexShrink: 0, marginTop: "4px" }}>
        <Icon name="calendar_month" size={18} />
        {t("dashboard.viewSchedule")}
      </a>
    </>
  );
}
