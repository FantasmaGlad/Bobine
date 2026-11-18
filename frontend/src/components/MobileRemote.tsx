"use client";

import React, { useState } from "react";
import type { CinemaRemoteState, PlaybackState } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import DisplayOutputSwitch from "@/components/DisplayOutputSwitch";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import { useVideoChapters } from "@/lib/chapters";
import type { DisplayOutput } from "@/lib/displayChannel";
import CinemaNowCard from "@/components/mobile-remote/CinemaNowCard";
import KioskControls from "@/components/mobile-remote/KioskControls";
import KioskNowCard from "@/components/mobile-remote/KioskNowCard";
import Icon from "@/components/Icon";
import LaunchSheet, { type BackgroundSummary, type PlaylistSummary, type VideoSummary } from "@/components/dashboard/LaunchSheet";

interface MobileRemoteProps {
  state: PlaybackState;
  livePosition: number;
  connected: boolean;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
  videos: VideoSummary[];
  playlists: PlaylistSummary[];
  backgrounds: BackgroundSummary[];
  getApiUrl: (path: string) => string;
  displayOutputCable: DisplayOutput | null;
  displayOutputNetwork: "kiosk" | "cinema" | null;
  cinemaLive: CinemaRemoteState | null;
  onCinemaPlayPause: () => void;
  onSetDisplayOutput: (channel: "cable" | "network", output: DisplayOutput) => void;
  channel?: "cable" | "network";
}

export default function MobileRemote({
  state,
  livePosition,
  connected,
  sendCommand,
  videos,
  playlists,
  backgrounds,
  getApiUrl,
  displayOutputCable,
  displayOutputNetwork,
  cinemaLive,
  onCinemaPlayPause,
  onSetDisplayOutput,
  channel,
}: MobileRemoteProps) {
  const { t } = useAppSettings();
  const [sheet, setSheet] = useState<"none" | "launch">("none");

  const channelCinema = (channel === "network" ? displayOutputNetwork : displayOutputCable) === "cinema";
  const channelRadio = channel !== "network" && displayOutputCable === "radio";

  if ((channelCinema || channelRadio) && sheet !== "none") setSheet("none");

  const isActive = state.current_video !== null || state.state === "playlist_waiting" || state.state === "background";
  const kioskChapters = useVideoChapters(state.current_video?.id, getApiUrl);
  const cinemaChapters = useVideoChapters(cinemaLive?.video_id, getApiUrl);

  const main = !connected ? (
    <div className="mobile-remote-empty">{t("mobileRemote.connectingHint")}</div>
  ) : channelRadio ? (
    <RadioRemotePanel key="radio_cable" channel="radio_cable" variant="compact" />
  ) : channelCinema ? (
    cinemaLive ? (
      <CinemaNowCard cinemaLive={cinemaLive} videos={videos} chapters={cinemaChapters} sendCommand={sendCommand} onPlayPause={onCinemaPlayPause} />
    ) : (
      <div className="mobile-remote-empty olc-anim-in">
        <p>{t("dashboard.cinemaNoPlayback")}</p>
      </div>
    )
  ) : !isActive ? (
    <div className="mobile-remote-empty olc-anim-in">
      <p>{t("mobileRemote.noCourseHint")}</p>
      <button className="btn btn-primary" style={{ height: "56px", marginTop: "16px" }} onClick={() => setSheet("launch")}>
        <Icon name="play_circle" size={20} />
        {t("mobileRemote.launchCourse")}
      </button>
    </div>
  ) : (
    <KioskNowCard state={state} livePosition={livePosition} getApiUrl={getApiUrl} chapters={kioskChapters} sendCommand={sendCommand} />
  );

  return (
    <div className="mobile-remote">
      {connected && (
        <div className="mobile-remote-output olc-anim-in">
          {(!channel || channel === "cable") && (
            <DisplayOutputSwitch
              displayOutput={displayOutputCable}
              onSetDisplayOutput={(output) => onSetDisplayOutput("cable", output)}
              label={t("dashboard.displayOutputCableLabel")}
              allowRadio
            />
          )}
          {(!channel || channel === "network") && (
            <DisplayOutputSwitch
              displayOutput={displayOutputNetwork}
              onSetDisplayOutput={(output) => onSetDisplayOutput("network", output)}
              label={t("dashboard.displayOutputNetworkLabel")}
            />
          )}
        </div>
      )}
      {main}
      {!channelCinema && (
        <KioskControls state={state} isActive={isActive} channel={channel} sendCommand={sendCommand} onLaunch={() => setSheet("launch")} />
      )}
      <LaunchSheet
        t={t} open={sheet !== "none"} onClose={() => setSheet("none")}
        videos={videos} playlists={playlists} backgrounds={backgrounds} sendCommand={sendCommand}
      />
    </div>
  );
}
