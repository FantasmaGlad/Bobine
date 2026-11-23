"use client";

import DisplayOutputSwitch from "@/components/DisplayOutputSwitch";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { screenUrl, type DisplayOutput, type LockedOutput } from "@/lib/displayChannel";
import { outputById, type OutputId } from "@/lib/outputs";

interface Props {
  channel: OutputId;
  connected: boolean;
  state: string;
  displayOutput: DisplayOutput | null;
  onSetDisplayOutput: (output: DisplayOutput) => void;
}

const STATES = ["waiting", "playing", "paused", "coach_mode", "offline", "playlist_waiting"];

const ACTIVE_LABEL: Record<LockedOutput, string> = {
  cinema: "dashboard.channelCinemaActive",
  radio: "dashboard.channelRadioActive",
  signage: "dashboard.channelSignageActive",
};

function lockedBy(output: DisplayOutput | null): LockedOutput | null {
  return output === null || output === "kiosk" ? null : output;
}

function pillClass(connected: boolean, locked: LockedOutput | null, state: string): string {
  if (!connected) return "down state-offline";
  if (locked) return "neutral";
  return state === "waiting" ? "waiting state-waiting" : `ok state-${state}`;
}

export default function ChannelCard({ channel, connected, state, displayOutput, onSetDisplayOutput }: Props) {
  const { t } = useAppSettings();
  const locked = lockedBy(displayOutput);
  const label = !connected ? t("dashboard.disconnected")
    : locked ? t(ACTIVE_LABEL[locked])
    : STATES.includes(state) ? t(`dashboard.stateLabels.${state}`) : state;
  const wired = outputById(channel).wired;
  const output = t(`outputs.${channel}`);
  return (
    <div className="live-block channel-card">
      <div className="channel-card-left">
        <h3>
          <Icon name={wired ? "cable" : "wifi"} size={18} />
          {wired ? t("dashboard.liveCableTitle") : t("dashboard.liveNetworkTitle", { output })}
        </h3>
        <span className={`status-pill ${pillClass(connected, locked, state)}`}>{label}</span>
      </div>
      <div className="channel-card-right">
        <DisplayOutputSwitch channel={channel} displayOutput={displayOutput} onSetDisplayOutput={onSetDisplayOutput}
          label={wired ? t("dashboard.displayOutputCableLabel") : t("dashboard.displayOutputNetworkLabel", { output })} />
        <a href={screenUrl(channel)} target="_blank" rel="noopener noreferrer" className="status-pill channel-card-open">
          <Icon name="open_in_new" size={14} />
          {t("dashboard.openScreen")}
        </a>
      </div>
    </div>
  );
}
