"use client";

import DisplayOutputSwitch from "@/components/DisplayOutputSwitch";
import Icon from "@/components/Icon";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import CinemaNowCard from "@/components/mobile-remote/CinemaNowCard";
import KioskNowCard from "@/components/mobile-remote/KioskNowCard";
import type { VideoSummary } from "@/components/dashboard/LaunchSheet";
import type { useVideoChapters } from "@/lib/chapters";
import type { DisplayOutput } from "@/lib/displayChannel";
import type { CinemaRemoteState, PlaybackState } from "@/lib/usePlaybackSocket";
import type { OutputId } from "@/lib/outputs";

type T = (key: string, vars?: Record<string, string | number>) => string;
type Chapters = ReturnType<typeof useVideoChapters>;

interface MainProps {
  connected: boolean;
  channelRadio: boolean;
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
  const { connected, channelRadio, channelCinema, isActive, state, livePosition, getApiUrl, kioskChapters, sendCommand, t } = props;
  if (!connected) return <div className="mobile-remote-empty">{t("mobileRemote.connectingHint")}</div>;
  if (channelRadio) return <RadioRemotePanel key="radio_cable" channel="radio_cable" variant="compact" />;
  if (channelCinema) return cinemaMain(props);
  if (!isActive) return idleMain(props);
  return <KioskNowCard state={state} livePosition={livePosition} getApiUrl={getApiUrl} chapters={kioskChapters} sendCommand={sendCommand} />;
}

interface SwitchProps {
  channel?: OutputId;
  displayOutputCable: DisplayOutput | null;
  displayOutputNetwork: DisplayOutput | null;
  onSetDisplayOutput: (channel: OutputId, output: DisplayOutput) => void;
  t: T;
}

export function OutputSwitches({ channel, displayOutputCable, displayOutputNetwork, onSetDisplayOutput, t }: SwitchProps) {
  return (
    <div className="mobile-remote-output olc-anim-in">
      {(!channel || channel === "cable") && (
        <DisplayOutputSwitch
          channel="cable"
          displayOutput={displayOutputCable}
          onSetDisplayOutput={(output) => onSetDisplayOutput("cable", output)}
          label={t("dashboard.displayOutputCableLabel")}
        />
      )}
      {(!channel || channel === "network") && (
        <DisplayOutputSwitch
          channel="network"
          displayOutput={displayOutputNetwork}
          onSetDisplayOutput={(output) => onSetDisplayOutput("network", output)}
          label={t("dashboard.displayOutputNetworkLabel")}
        />
      )}
    </div>
  );
}
