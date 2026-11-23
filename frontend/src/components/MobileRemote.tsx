"use client";

import React, { useState } from "react";
import type { CinemaRemoteState, PlaybackState } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useVideoChapters } from "@/lib/chapters";
import type { DisplayOutput } from "@/lib/displayChannel";
import KioskControls from "@/components/mobile-remote/KioskControls";
import { OutputSwitches, RemoteMain } from "@/components/mobile-remote/RemoteMain";
import SignagePanel from "@/components/dashboard/SignagePanel";
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
  displayOutputNetwork: DisplayOutput | null;
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

  const channelOutput = channel === "network" ? displayOutputNetwork : displayOutputCable;
  const channelCinema = channelOutput === "cinema";
  const channelSignage = channelOutput === "signage";
  const channelRadio = channel !== "network" && displayOutputCable === "radio";

  if ((channelCinema || channelRadio || channelSignage) && sheet !== "none") setSheet("none");

  const isActive = state.current_video !== null || state.state === "playlist_waiting" || state.state === "background";
  const kioskChapters = useVideoChapters(state.current_video?.id, getApiUrl);
  const cinemaChapters = useVideoChapters(cinemaLive?.video_id, getApiUrl);

  const main = connected && channelSignage ? <SignagePanel channel={channel ?? "cable"} backgrounds={backgrounds} /> : (
    <RemoteMain
      connected={connected} channelRadio={channelRadio} channelCinema={channelCinema} isActive={isActive}
      cinemaLive={cinemaLive} cinemaChapters={cinemaChapters} kioskChapters={kioskChapters} state={state} livePosition={livePosition}
      videos={videos} getApiUrl={getApiUrl} sendCommand={sendCommand} onCinemaPlayPause={onCinemaPlayPause} onLaunch={() => setSheet("launch")} t={t}
    />
  );

  return (
    <div className="mobile-remote">
      {connected && (
        <OutputSwitches channel={channel} displayOutputCable={displayOutputCable} displayOutputNetwork={displayOutputNetwork} onSetDisplayOutput={onSetDisplayOutput} t={t} />
      )}
      {main}
      {!channelCinema && !channelSignage && (
        <KioskControls state={state} isActive={isActive} channel={channel} sendCommand={sendCommand} onLaunch={() => setSheet("launch")} />
      )}
      <LaunchSheet
        t={t} open={sheet !== "none"} onClose={() => setSheet("none")}
        videos={videos} playlists={playlists} backgrounds={backgrounds} sendCommand={sendCommand}
      />
    </div>
  );
}
