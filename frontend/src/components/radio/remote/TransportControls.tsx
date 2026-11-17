"use client";

import React from "react";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { RadioRepeatMode } from "@/lib/useRadioSocket";
import type { SendRadioCommand } from "./types";

const REPEAT_CYCLE: RadioRepeatMode[] = ["off", "playlist", "track"];

interface TransportControlsProps {
  playing: boolean;
  shuffle: boolean;
  repeat: RadioRepeatMode;
  sendCommand: SendRadioCommand;
}

export default function TransportControls({ playing, shuffle, repeat, sendCommand }: TransportControlsProps) {
  const { t } = useAppSettings();
  const playLabel = playing ? t("radioRemote.pause") : t("radioRemote.play");
  const repeatLabel =
    repeat === "track" ? t("radioRemote.repeatTrack") : repeat === "playlist" ? t("radioRemote.repeatPlaylist") : t("radioRemote.repeatOff");
  const cycleRepeat = () => {
    const next = REPEAT_CYCLE[(REPEAT_CYCLE.indexOf(repeat) + 1) % REPEAT_CYCLE.length];
    sendCommand("radio_set_repeat", { mode: next });
  };
  return (
    <div className="live-controls live-controls--icons">
      <button className="btn btn-secondary control-btn" onClick={() => sendCommand("stop")} aria-label={t("radioRemote.stop")} title={t("radioRemote.stop")}>
        <Icon name="stop" size={18} />
        <span className="control-label">{t("radioRemote.stop")}</span>
      </button>
      <button className="btn btn-secondary control-btn control-btn-icon" onClick={() => sendCommand("radio_previous_track")} title={t("radioRemote.previousTrack")} aria-label={t("radioRemote.previousTrack")}>
        <Icon name="skip_previous" size={20} filled />
      </button>
      <button className="btn btn-primary control-btn control-btn-main" onClick={() => sendCommand(playing ? "pause" : "play")} aria-label={playLabel} title={playLabel}>
        <Icon name={playing ? "pause" : "play_arrow"} size={22} filled />
        <span className="control-label">{playLabel}</span>
      </button>
      <button className="btn btn-secondary control-btn control-btn-icon" onClick={() => sendCommand("radio_next_track")} title={t("radioRemote.nextTrack")} aria-label={t("radioRemote.nextTrack")}>
        <Icon name="skip_next" size={20} filled />
      </button>
      <button
        className={`btn ${shuffle ? "btn-primary" : "btn-secondary"} control-btn control-btn-pill`}
        onClick={() => sendCommand("radio_set_shuffle", { on: !shuffle })}
        title={t("radioRemote.shuffleLabel")}
        aria-label={t("radioRemote.shuffleLabel")}
        aria-pressed={shuffle}
      >
        <Icon name="shuffle" size={16} />
        <span className="control-label">{t("radioRemote.shuffleLabel")}</span>
      </button>
      <button
        className={`btn ${repeat !== "off" ? "btn-primary" : "btn-secondary"} control-btn control-btn-pill`}
        onClick={cycleRepeat}
        title={repeatLabel}
        aria-label={repeatLabel}
        aria-pressed={repeat !== "off"}
      >
        <Icon name={repeat === "track" ? "repeat_one" : "repeat"} size={16} />
        <span className="control-label">{repeatLabel}</span>
      </button>
    </div>
  );
}
