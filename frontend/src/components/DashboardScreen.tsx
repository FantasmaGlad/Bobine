"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useNowPlaying } from "@/components/cinema/useNowPlaying";
import AmbianceModal from "@/components/dashboard/AmbianceModal";
import ChannelCard from "@/components/dashboard/ChannelCard";
import LaunchPanel from "@/components/dashboard/LaunchPanel";
import LiveHero from "@/components/dashboard/LiveHero";
import { CoachModeNotice, InterruptedBanner } from "@/components/dashboard/Notices";
import SignagePanel from "@/components/dashboard/SignagePanel";
import { ActionCards, UpcomingList } from "@/components/dashboard/SideCards";
import { setDisplayOutput, useDashboardData } from "@/components/dashboard/useDashboardData";
import MobileRemote from "@/components/MobileRemote";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import { getApiUrl } from "@/lib/apiUrl";
import { useInterpolatedPosition } from "@/lib/useInterpolatedPosition";
import { useIsMobile } from "@/lib/useIsMobile";
import { hasMode, outputById, type OutputId } from "@/lib/outputs";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";

export default function DashboardScreen({ channel }: { channel: OutputId }) {
  const isMobile = useIsMobile();
  const router = useRouter();
  const [lastCause, setLastCause] = useState("sync");
  const [ambianceOpen, setAmbianceOpen] = useState(false);
  const { state, connected, sendCommand, displayOutputs, cinemaLocked, lockedReason, cinemaState } =
    usePlaybackSocket((evt) => setLastCause(evt.cause), undefined, channel, undefined, "dashboard");
  const livePosition = useInterpolatedPosition(state.position_seconds, state.state === "playing", lastCause);
  const remote = useNowPlaying(cinemaState, sendCommand);
  const data = useDashboardData(channel);
  const spec = outputById(channel);
  const displayOutput = displayOutputs[channel] ?? null;
  const cinema = displayOutput === "cinema";
  const radio = hasMode(channel, "radio") && displayOutput === "radio" && spec.radioChannel !== null;
  const signage = displayOutput === "signage";
  const coach = spec.coach && state.state === "coach_mode";

  useEffect(() => {
    if (coach) router.replace("/coach");
  }, [coach, router]);

  if (isMobile) {
    return (
      <MobileRemote state={state} livePosition={livePosition} connected={connected} sendCommand={sendCommand} videos={data.videos} playlists={data.playlists}
        backgrounds={data.backgrounds} getApiUrl={getApiUrl} displayOutputs={displayOutputs}
        cinemaLive={remote.nowPlaying} onCinemaPlayPause={remote.playPause} onSetDisplayOutput={setDisplayOutput} channel={channel} />
    );
  }
  if (coach) return <CoachModeNotice />;

  const channelCard = (
    <ChannelCard channel={channel} connected={connected} state={state.state} displayOutput={displayOutput}
      onSetDisplayOutput={(output) => setDisplayOutput(channel, output)} />
  );

  if (radio) {
    return (
      <div className="dashboard-container">
        {channelCard}
        {spec.radioChannel && <RadioRemotePanel key={spec.radioChannel} channel={spec.radioChannel} />}
      </div>
    );
  }

  if (signage) {
    return (
      <div className="dashboard-container">
        {channelCard}
        <SignagePanel channel={channel} />
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {data.interrupted && <InterruptedBanner data={data} />}
      {channelCard}
      <div className="dashboard-bento-grid" style={cinema ? { gridTemplateColumns: "1fr" } : undefined}>
        <div className="bento-col-main">
          <LiveHero channel={channel} cinema={cinema} state={state} livePosition={livePosition} remote={remote} videos={data.videos} backgrounds={data.backgrounds} sendCommand={sendCommand} />
          {!cinema && <ActionCards channel={channel} locked={cinemaLocked} onAmbiance={() => setAmbianceOpen(true)} />}
          {!cinema && <UpcomingList channel={channel} upcoming={data.upcoming} />}
        </div>
        {!cinema && <LaunchPanel channel={channel} videos={data.videos} playlists={data.playlists} locked={cinemaLocked} lockedReason={lockedReason} sendCommand={sendCommand} />}
      </div>
      {ambianceOpen && (
        <AmbianceModal backgrounds={data.backgrounds} onClose={() => setAmbianceOpen(false)}
          onLaunch={(bg) => { sendCommand("load_background", { background_id: bg.id }); setAmbianceOpen(false); }} />
      )}
    </div>
  );
}
