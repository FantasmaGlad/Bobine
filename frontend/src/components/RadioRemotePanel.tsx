"use client";

import React, { useState } from "react";
import Link from "next/link";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import NowPlayingCard from "@/components/radio/remote/NowPlayingCard";
import PlaylistLauncher from "@/components/radio/remote/PlaylistLauncher";
import QueuePanel from "@/components/radio/remote/QueuePanel";
import type { RadioChannelId } from "@/lib/displayChannel";
import { useInterpolatedPosition } from "@/lib/useInterpolatedPosition";
import { RadioEvent, useRadioSocket } from "@/lib/useRadioSocket";

interface RadioRemotePanelProps {
  channel: RadioChannelId;
  variant?: "full" | "compact";
}

export default function RadioRemotePanel({ channel, variant = "full" }: RadioRemotePanelProps) {
  const { t } = useAppSettings();
  const [lastCause, setLastCause] = useState("sync");
  const handleRadioEvent = (evt: RadioEvent) => setLastCause(evt.cause);
  const { state, connected, sendCommand } = useRadioSocket(handleRadioEvent, undefined, channel);
  const livePosition = useInterpolatedPosition(state.position_seconds, state.playing, lastCause);

  return (
    <>
      <NowPlayingCard state={state} connected={connected} livePosition={livePosition} sendCommand={sendCommand} />
      <div className="dashboard-bento-grid" style={variant === "compact" ? { gridTemplateColumns: "1fr" } : undefined}>
        <div className="bento-col-main">
          <PlaylistLauncher sendCommand={sendCommand} />
          <Link href="/settings/?vue=sound" className="btn btn-secondary radio-sound-link">
            <Icon name="graphic_eq" size={18} />
            {t("radioRemote.soundSettings")}
          </Link>
        </div>
        {variant === "full" && (
          <div className="bento-col-side">
            <QueuePanel state={state} sendCommand={sendCommand} />
          </div>
        )}
      </div>
    </>
  );
}
