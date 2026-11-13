"use client";

import { useState } from "react";

import Icon from "@/components/Icon";
import ResponsiveSelect from "@/components/ResponsiveSelect";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { courseThumbSrc, formatClock } from "@/lib/courseMeta";
import { formatMinutes } from "@/lib/format";

import type { PlaylistSummary, Send, VideoSummary } from "./types";

interface Props {
  isCable: boolean;
  videos: VideoSummary[];
  playlists: PlaylistSummary[];
  locked: boolean;
  lockedReason: string | null | undefined;
  sendCommand: Send;
}

function Launcher({ value, onChange, placeholder, options, disabled, title, icon, onLaunch }: {
  value: string; onChange: (value: string) => void; placeholder: string; options: Parameters<typeof ResponsiveSelect>[0]["options"];
  disabled: boolean; title?: string; icon: string; onLaunch: () => void;
}) {
  const { t } = useAppSettings();
  return (
    <div className="launch-row launch-row--stacked">
      <ResponsiveSelect style={{ flex: 1, minWidth: 0 }} value={value} onChange={onChange} placeholder={placeholder} title={placeholder} options={options} />
      <button className="btn btn-primary" onClick={onLaunch} disabled={disabled} title={title}>
        <Icon name={icon} size={16} filled={icon === "play_arrow"} />
        {t("dashboard.launch")}
      </button>
    </div>
  );
}

export default function LaunchPanel({ isCable, videos, playlists, locked, lockedReason, sendCommand }: Props) {
  const { t } = useAppSettings();
  const [videoId, setVideoId] = useState("");
  const [playlistId, setPlaylistId] = useState("");
  const lockHint = t(lockedReason === "radio" ? "dashboard.channelRadioLockedHint" : "dashboard.channelCinemaLockedHint");
  return (
    <div className="bento-col-side">
      <div className="launch-block">
        <h3>
          <Icon name={isCable ? "cable" : "wifi"} size={18} />
          {isCable ? t("dashboard.launchCourseCableTitle") : t("dashboard.launchCourseNetworkTitle")}
        </h3>
        <p className="launch-block-hint">{isCable ? t("dashboard.launchCourseCableHint") : t("dashboard.launchCourseNetworkHint")}</p>
        <Launcher
          value={videoId} onChange={setVideoId} placeholder={t("dashboard.chooseVideo")} icon="play_arrow"
          disabled={!videoId || locked} title={locked ? lockHint : undefined}
          onLaunch={() => videoId && sendCommand("load", { video_id: Number(videoId) })}
          options={videos.map((v) => ({
            value: String(v.id), label: v.title,
            sublabel: [v.program, v.release ? `#${v.release}` : null].filter(Boolean).join(" · ") || undefined,
            thumbnail: courseThumbSrc(getApiUrl, v), meta: v.duration_seconds ? formatClock(v.duration_seconds) : undefined,
          }))}
        />
        {videos.length === 0 && <p className="live-empty" style={{ marginTop: "12px" }}>{t("dashboard.noVideos")}</p>}
        {locked && <p className="live-empty" role="alert" style={{ marginTop: "12px", color: "var(--accent-text)" }}>{lockHint}</p>}
      </div>
      <div className="launch-block">
        <h3>
          <Icon name="playlist_play" size={18} />
          {t("dashboard.launchPlaylistTitle")}
        </h3>
        <Launcher
          value={playlistId} onChange={setPlaylistId} placeholder={t("dashboard.choosePlaylist")} icon="playlist_play"
          disabled={!playlistId || locked} title={locked ? lockHint : undefined}
          onLaunch={() => playlistId && sendCommand("load_playlist", { playlist_id: Number(playlistId) })}
          options={playlists.map((p) => ({
            value: String(p.id), label: p.name, sublabel: t("dashboard.playlistCourseCount", { count: p.item_count }),
            thumbnail: courseThumbSrc(getApiUrl, { thumbnail_path: p.thumbnail_path }), meta: formatMinutes(p.total_duration_seconds, "0 min"),
          }))}
        />
        {playlists.length === 0 && <p className="live-empty" style={{ marginTop: "12px" }}>{t("dashboard.noPlaylists")}</p>}
      </div>
    </div>
  );
}
