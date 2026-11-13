"use client";

import AppLogo from "@/components/AppLogo";
import Icon from "@/components/Icon";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { thumbnailUrl, type CinemaVideo } from "@/lib/cinemaCatalog";
import { formatCleanDescription } from "@/lib/formatDescription";
import { formatTime } from "@/lib/format";
import { getAudioQualityBadge, getResolutionBadge } from "@/lib/videoBadges";

interface Props {
  video: CinemaVideo | null;
  position: number;
  duration: number;
  onResume: () => void;
  onBack: () => void;
}

function Header({ video }: { video: CinemaVideo | null }) {
  const { t } = useAppSettings();
  const resolution = getResolutionBadge(video?.width, video?.height, "HD");
  const audio = getAudioQualityBadge(video?.audio_channels, video?.audio_codec, t("audioBadge.stereo"), t);
  return (
    <div>
      <div className="pause-header-row">
        <span className="cinema-pause-kicker">{t("cinema.pause")}</span>
        {video?.program && <span className="cinema-pause-badge" style={{ color: "var(--accent-primary)" }}>{video.program}</span>}
        {video?.release && <span className="cinema-pause-year">{video.release}</span>}
        {resolution && <span className="cinema-pause-badge-pill">{resolution}</span>}
        {audio && <span className="cinema-pause-badge-pill">{audio}</span>}
      </div>
      <h2 className="cinema-pause-title">{video?.title}</h2>
    </div>
  );
}

function Thumb({ video, position, duration, onResume }: Omit<Props, "onBack">) {
  const { t } = useAppSettings();
  const thumb = video ? thumbnailUrl(video) : null;
  return (
    <div className="pause-media-col">
      <div className="pause-thumb-wrap" onClick={onResume} title={t("cinema.play")}>
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt={video!.title} className="pause-thumb-img" />
        ) : (
          <div className="pause-thumb-fallback"><AppLogo size={90} className="pause-logo" /></div>
        )}
        <div className="pause-thumb-overlay-btn"><Icon name="play_arrow" size={48} filled /></div>
        <div className="pause-thumb-time">{formatTime(position)} / {formatTime(duration)}</div>
      </div>
      <div className="pause-logo-mini-wrap"><AppLogo size={80} className="pause-logo" /></div>
    </div>
  );
}

export default function PauseOverlay(props: Props) {
  const { t } = useAppSettings();
  const { video, onResume, onBack } = props;
  return (
    <div className="cinema-pause-overlay" onClick={onResume}>
      <div className="cinema-pause-center" onClick={(e) => e.stopPropagation()}>
        <Thumb {...props} />
        <div className="pause-details-col">
          <Header video={video} />
          {video?.description ? (
            <div className="pause-description-scroll">
              <p className="cinema-pause-description-text">{formatCleanDescription(video.description)}</p>
            </div>
          ) : (
            <div style={{ flex: 1 }} />
          )}
          <div className="pause-actions-row">
            <button className="pause-resume-btn-pill" onClick={onResume} title={t("cinema.play")}>
              <Icon name="play_arrow" size={24} filled />
              <span>{t("cinema.play")}</span>
            </button>
            <button className="pause-back-btn-pill" onClick={onBack} title={t("cinema.backToMenu")}>
              <Icon name="arrow_back" size={20} />
              <span>{t("cinema.backToMenu")}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
