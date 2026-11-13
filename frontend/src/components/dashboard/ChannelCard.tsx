"use client";

import DisplayOutputSwitch from "@/components/DisplayOutputSwitch";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { DisplayOutput } from "@/lib/displayChannel";

interface Props {
  isCable: boolean;
  connected: boolean;
  state: string;
  displayOutput: DisplayOutput | null;
  cinema: boolean;
  radio: boolean;
  onSetDisplayOutput: (output: DisplayOutput) => void;
}

const STATES = ["waiting", "playing", "paused", "coach_mode", "offline", "playlist_waiting"];

function pillClass({ connected, cinema, radio, state }: Props): string {
  if (!connected) return "down state-offline";
  if (cinema || radio) return "neutral";
  return state === "waiting" ? "waiting state-waiting" : `ok state-${state}`;
}

export default function ChannelCard(props: Props) {
  const { t } = useAppSettings();
  const { isCable, connected, state, displayOutput, cinema, radio, onSetDisplayOutput } = props;
  const label = !connected ? t("dashboard.disconnected")
    : radio ? t("dashboard.channelRadioActive")
    : cinema ? t("dashboard.channelCinemaActive")
    : STATES.includes(state) ? t(`dashboard.stateLabels.${state}`) : state;
  return (
    <div className="live-block channel-card">
      <div className="channel-card-left">
        <h3>
          <Icon name={isCable ? "cable" : "wifi"} size={18} />
          {isCable ? t("dashboard.liveCableTitle") : t("dashboard.liveNetworkTitle")}
        </h3>
        <span className={`status-pill ${pillClass(props)}`}>{label}</span>
      </div>
      <div className="channel-card-right">
        <DisplayOutputSwitch displayOutput={displayOutput} onSetDisplayOutput={onSetDisplayOutput}
          label={isCable ? t("dashboard.displayOutputCableLabel") : t("dashboard.displayOutputNetworkLabel")} allowRadio={isCable} />
        {radio && (
          <a href="/radio?channel=cable" target="_blank" rel="noopener noreferrer" className="status-pill" style={{ textDecoration: "none" }}>{t("radioRemote.openPlayer")}</a>
        )}
        {!isCable && (
          <a href={`/${displayOutput === "cinema" ? "cinema" : "kiosk"}?channel=network`} target="_blank" rel="noopener noreferrer" className="status-pill" style={{ textDecoration: "none" }}>
            {t("dashboard.openNetworkScreen")}
          </a>
        )}
      </div>
    </div>
  );
}
