import CourseCard from "@/components/CourseCard";
import Icon from "@/components/Icon";
import { formatClock } from "@/lib/courseMeta";
import { formatCleanDescription } from "@/lib/formatDescription";
import { getAudioQualityBadge, getResolutionBadge } from "@/lib/videoBadges";
import type { VideoSummary } from "../LaunchSheet";

type T = (key: string, vars?: Record<string, string | number>) => string;

export function LaunchPreview({ video, t }: { video: VideoSummary; t: T }) {
  const resolution = getResolutionBadge(video.width, video.height);
  const audio = getAudioQualityBadge(video.audio_channels, video.audio_codec, null, t);
  return (
    <div className="launch-preview">
      <CourseCard
        variant="hero"
        releaseLabel={(release: string) => t("mobileRemote.releaseShort", { release })}
        fallbackProgram={t("mobileRemote.otherProgram")}
        course={video}
      />
      <div className="launch-preview__specs">
        {resolution && <span>{resolution}</span>}
        {audio && <span>{audio}</span>}
        {video.duration_seconds ? <span>{formatClock(video.duration_seconds)}</span> : null}
      </div>
      {video.description ? <p className="launch-preview__description">{formatCleanDescription(video.description)}</p> : null}
    </div>
  );
}

export function PreviewFooter({ onBack, onLaunch, t }: { onBack: () => void; onLaunch: () => void; t: T }) {
  return (
    <>
      <button type="button" className="btn btn-secondary" onClick={onBack}>
        {t("mobileRemote.back")}
      </button>
      <button type="button" className="btn btn-primary" onClick={onLaunch}>
        <Icon name="play_arrow" size={20} filled />
        {t("mobileRemote.launchNow")}
      </button>
    </>
  );
}
