"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useNowPlaying } from "@/components/cinema/useNowPlaying";
import AmbianceModal from "@/components/dashboard/AmbianceModal";
import ChannelCard from "@/components/dashboard/ChannelCard";
import LaunchPanel from "@/components/dashboard/LaunchPanel";
import LiveHero from "@/components/dashboard/LiveHero";
import { CoachModeNotice, InterruptedBanner } from "@/components/dashboard/Notices";
import { ActionCards, UpcomingList } from "@/components/dashboard/SideCards";
import { setDisplayOutput, useDashboardData } from "@/components/dashboard/useDashboardData";
import MobileRemote from "@/components/MobileRemote";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import { getApiUrl } from "@/lib/apiUrl";
import { useInterpolatedPosition } from "@/lib/useInterpolatedPosition";
import { useIsMobile } from "@/lib/useIsMobile";
import { usePlaybackSocket, type PlaybackChannel } from "@/lib/usePlaybackSocket";

export default function DashboardScreen({ channel }: { channel: PlaybackChannel }) {
  const isMobile = useIsMobile();
  const router = useRouter();
  const [lastCause, setLastCause] = useState("sync");
  const [ambianceOpen, setAmbianceOpen] = useState(false);
  const { state, connected, sendCommand, displayOutputCable, displayOutputNetwork, cinemaLocked, lockedReason, cinemaState } =
    usePlaybackSocket((evt) => setLastCause(evt.cause), undefined, channel, undefined, "dashboard");
  const livePosition = useInterpolatedPosition(state.position_seconds, state.state === "playing", lastCause);
  const remote = useNowPlaying(cinemaState, sendCommand);
  const data = useDashboardData(channel);
  const isCable = channel === "cable";
  const displayOutput = isCable ? displayOutputCable : displayOutputNetwork;
  const cinema = displayOutput === "cinema";
  const radio = isCable && displayOutputCable === "radio";
  const coach = isCable && state.state === "coach_mode";

  useEffect(() => {
    if (coach) router.replace("/coach");
  }, [coach, router]);

  if (isMobile) {
    return (
      <MobileRemote state={state} livePosition={livePosition} connected={connected} sendCommand={sendCommand} videos={data.videos} playlists={data.playlists}
        backgrounds={data.backgrounds} getApiUrl={getApiUrl} displayOutputCable={displayOutputCable} displayOutputNetwork={displayOutputNetwork}
        cinemaLive={remote.nowPlaying} onCinemaPlayPause={remote.playPause} onSetDisplayOutput={setDisplayOutput} channel={channel} />
    );
  }
  if (coach) return <CoachModeNotice />;

  const channelCard = (
    <ChannelCard isCable={isCable} connected={connected} state={state.state} displayOutput={displayOutput} cinema={cinema} radio={radio}
      onSetDisplayOutput={(output) => setDisplayOutput(channel, output)} />
  );

  if (radio) {
    return (
      <div className="dashboard-container">
        {channelCard}
        <RadioRemotePanel key="radio_cable" channel="radio_cable" />
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {data.interrupted && <InterruptedBanner data={data} />}
      {channelCard}
      <div className="dashboard-bento-grid" style={cinema ? { gridTemplateColumns: "1fr" } : undefined}>
        <div className="bento-col-main">
          <LiveHero isCable={isCable} cinema={cinema} state={state} livePosition={livePosition} remote={remote} videos={data.videos} backgrounds={data.backgrounds} sendCommand={sendCommand} />
          {!cinema && <ActionCards isCable={isCable} locked={cinemaLocked} onAmbiance={() => setAmbianceOpen(true)} />}
          {!cinema && <UpcomingList channel={channel} upcoming={data.upcoming} />}
        </div>
        {!cinema && <LaunchPanel isCable={isCable} videos={data.videos} playlists={data.playlists} locked={cinemaLocked} lockedReason={lockedReason} sendCommand={sendCommand} />}
      </div>
      {ambianceOpen && (
        <AmbianceModal backgrounds={data.backgrounds} onClose={() => setAmbianceOpen(false)}
          onLaunch={(bg) => { sendCommand("load_background", { background_id: bg.id }); setAmbianceOpen(false); }} />
      )}
    </div>
  );
}
