"use client";

import DisplayOutputSwitch from "@/components/DisplayOutputSwitch";
import Icon from "@/components/Icon";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import CinemaNowCard from "@/components/mobile-remote/CinemaNowCard";
import KioskNowCard from "@/components/mobile-remote/KioskNowCard";
import type { VideoSummary } from "@/components/dashboard/LaunchSheet";
import type { useVideoChapters } from "@/lib/chapters";
import type { DisplayOutput, DisplayOutputs } from "@/lib/displayChannel";
import type { CinemaRemoteState, PlaybackState } from "@/lib/usePlaybackSocket";
import { OUTPUTS, type OutputId, type RadioChannelId } from "@/lib/outputs";

type T = (key: string, vars?: Record<string, string | number>) => string;
type Chapters = ReturnType<typeof useVideoChapters>;

interface MainProps {
  connected: boolean;
  radioChannel: RadioChannelId | null;
  channelCinema: boolean;
  isActive: boolean;
  cinemaLive: CinemaRemoteState | null;
  cinemaChapters: Chapters;
  kioskChapters: Chapters;
  state: PlaybackState;
  livePosition: number;
  videos: VideoSummary[];
  getApiUrl: (path: string) => string;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
  onCinemaPlayPause: () => void;
  onLaunch: () => void;
  t: T;
}

function cinemaMain({ cinemaLive, videos, cinemaChapters, sendCommand, onCinemaPlayPause, t }: MainProps) {
  if (cinemaLive) {
    return <CinemaNowCard cinemaLive={cinemaLive} videos={videos} chapters={cinemaChapters} sendCommand={sendCommand} onPlayPause={onCinemaPlayPause} />;
  }
  return (
    <div className="mobile-remote-empty olc-anim-in">
      <p>{t("dashboard.cinemaNoPlayback")}</p>
    </div>
  );
}

function idleMain({ onLaunch, t }: MainProps) {
  return (
    <div className="mobile-remote-empty olc-anim-in">
      <p>{t("mobileRemote.noCourseHint")}</p>
      <button className="btn btn-primary" style={{ height: "56px", marginTop: "16px" }} onClick={onLaunch}>
        <Icon name="play_circle" size={20} />
        {t("mobileRemote.launchCourse")}
      </button>
    </div>
  );
}

export function RemoteMain(props: MainProps) {
  const { connected, radioChannel, channelCinema, isActive, state, livePosition, getApiUrl, kioskChapters, sendCommand, t } = props;
  if (!connected) return <div className="mobile-remote-empty">{t("mobileRemote.connectingHint")}</div>;
  if (radioChannel) return <RadioRemotePanel key={radioChannel} channel={radioChannel} variant="compact" />;
  if (channelCinema) return cinemaMain(props);
  if (!isActive) return idleMain(props);
  return <KioskNowCard state={state} livePosition={livePosition} getApiUrl={getApiUrl} chapters={kioskChapters} sendCommand={sendCommand} />;
}

interface SwitchProps {
  channel?: OutputId;
  displayOutputs: DisplayOutputs;
  onSetDisplayOutput: (channel: OutputId, output: DisplayOutput) => void;
  t: T;
}

export function OutputSwitches({ channel, displayOutputs, onSetDisplayOutput, t }: SwitchProps) {
  return (
    <div className="mobile-remote-output olc-anim-in">
      {OUTPUTS.filter((output) => !channel || channel === output.id).map((output) => (
        <DisplayOutputSwitch
          key={output.id}
          channel={output.id}
          displayOutput={displayOutputs[output.id] ?? null}
          onSetDisplayOutput={(mode) => onSetDisplayOutput(output.id, mode)}
          label={output.wired ? t("dashboard.displayOutputCableLabel") : t("dashboard.displayOutputNetworkLabel", { output: t(`outputs.${output.id}`) })}
        />
      ))}
    </div>
  );
}
