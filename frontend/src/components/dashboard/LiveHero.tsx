"use client";

import type { NowPlaying } from "@/components/cinema/useNowPlaying";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { CinemaRemoteState, PlaybackState } from "@/lib/usePlaybackSocket";

import { PlaylistBar, PlaylistWaiting } from "./KioskPlaylist";
import KioskPlayer from "./KioskPlayer";
import LiveCinema from "./LiveCinema";
import { thumbnailOf, type BackgroundSummary, type Send, type VideoSummary } from "./types";

interface Props {
  isCable: boolean;
  cinema: boolean;
  state: PlaybackState;
  livePosition: number;
  remote: NowPlaying<CinemaRemoteState>;
  videos: VideoSummary[];
  backgrounds: BackgroundSummary[];
  sendCommand: Send;
}

function Kiosk({ state, livePosition, backgroundThumb, sendCommand }: Pick<Props, "state" | "livePosition" | "sendCommand"> & { backgroundThumb: string | null }) {
  const { t } = useAppSettings();
  const index = state.playlist_index;
  const next = state.playlist_items && index !== null && index !== undefined ? state.playlist_items[index + 1] : null;
  return (
    <>
      {state.playlist_name && <PlaylistBar state={state} sendCommand={sendCommand} />}
      {state.playlist_name && state.state !== "playlist_waiting" && next && (
        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "12px" }}>{t("dashboard.nextCourseLabel", { title: next.title })}</div>
      )}
      {state.state === "playlist_waiting"
        ? <PlaylistWaiting state={state} next={next} sendCommand={sendCommand} />
        : <KioskPlayer state={state} livePosition={livePosition} backgroundThumb={backgroundThumb} sendCommand={sendCommand} />}
    </>
  );
}

export default function LiveHero({ isCable, cinema, state, livePosition, remote, videos, backgrounds, sendCommand }: Props) {
  const { t } = useAppSettings();
  const active = state.current_video !== null || state.state === "playlist_waiting" || state.state === "background";
  const live = remote.nowPlaying;
  const cinemaVideo = live?.video_id ? videos.find((v) => v.id === live.video_id) ?? null : null;
  const cinemaThumb = thumbnailOf(cinemaVideo?.thumbnail_path);
  const backgroundThumb = thumbnailOf(backgrounds.find((b) => b.id === state.current_background?.id)?.thumbnail_path);
  const kioskThumb = state.state === "background" ? backgroundThumb : state.current_video?.thumbnail_url ? thumbnailOf(state.current_video.thumbnail_url) : null;
  const backdrop = cinema ? (live ? cinemaThumb : null) : active ? kioskThumb : null;
  return (
    <div className="live-block bento-hero-live">
      {backdrop && <div className="bento-hero-backdrop" style={{ backgroundImage: `url("${backdrop}")` }} />}
      <div className="bento-hero-content">
        <div className="live-header">
          <h3>
            <Icon name="play_circle" size={18} />
            {t("dashboard.liveTitle")}
          </h3>
          <p className="live-block-hint" style={{ margin: 0 }}>{isCable ? t("dashboard.liveChannelHintCable") : t("dashboard.liveChannelHintNetwork")}</p>
        </div>
        {cinema ? <LiveCinema remote={remote} video={cinemaVideo} thumb={cinemaThumb} sendCommand={sendCommand} />
          : active ? <Kiosk state={state} livePosition={livePosition} backgroundThumb={backgroundThumb} sendCommand={sendCommand} />
          : <div className="live-empty">{t("dashboard.emptyLive")}</div>}
      </div>
    </div>
  );
}
