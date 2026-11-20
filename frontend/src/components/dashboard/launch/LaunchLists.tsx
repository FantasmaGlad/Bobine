import CourseCard from "@/components/CourseCard";
import Icon from "@/components/Icon";
import { courseThumbSrc } from "@/lib/courseMeta";
import type { BackgroundSummary, PlaylistSummary, VideoSummary } from "../LaunchSheet";

type T = (key: string, vars?: Record<string, string | number>) => string;

export type LaunchTab = "videos" | "playlists" | "backgrounds";

interface ListsProps {
  tab: LaunchTab;
  videos: VideoSummary[];
  playlists: PlaylistSummary[];
  backgrounds: BackgroundSummary[];
  onPreview: (id: number) => void;
  onLaunch: (command: string, params: Record<string, unknown>) => void;
  t: T;
}

function VideoList({ videos, onPreview, t }: ListsProps) {
  return videos.map((v) => (
    <CourseCard
      key={`v-${v.id}`}
      releaseLabel={(release: string) => t("mobileRemote.releaseShort", { release })}
      fallbackProgram={t("mobileRemote.otherProgram")}
      course={v}
      onClick={() => onPreview(v.id)}
      trailing={<Icon name="chevron_right" size={20} style={{ alignSelf: "center", color: "var(--text-muted)" }} />}
    />
  ));
}

function PlaylistOptions({ playlists, onLaunch, t }: ListsProps) {
  return playlists.map((p) => (
    <button key={`pl-${p.id}`} type="button" className="sheet-option olc-press" onClick={() => onLaunch("load_playlist", { playlist_id: p.id })}>
      <Icon name="playlist_play" size={22} />
      <span className="sheet-option__text">
        <span className="sheet-option__label">{p.name}</span>
        <span className="sheet-option__sub">{t("mobileRemote.coursesCount", { count: p.item_count })}</span>
      </span>
    </button>
  ));
}

function BackgroundOptions({ backgrounds, onLaunch, t }: ListsProps) {
  return backgrounds.map((b) => {
    const thumb = courseThumbSrc({ thumbnail_path: b.thumbnail_path });
    return (
      <button key={`bg-${b.id}`} type="button" className="sheet-option olc-press" onClick={() => onLaunch("load_background", { background_id: b.id })}>
        {thumb ? <img className="sheet-option__thumb" src={thumb} alt="" loading="lazy" /> : <Icon name="gradient" size={22} />}
        <span className="sheet-option__text">
          <span className="sheet-option__label">{b.title}</span>
          <span className="sheet-option__sub">{t("mobileRemote.backgroundLabel")}</span>
        </span>
      </button>
    );
  });
}

export default function LaunchLists(props: ListsProps) {
  const { tab, videos, playlists, backgrounds, t } = props;
  const count = tab === "videos" ? videos.length : tab === "playlists" ? playlists.length : backgrounds.length;
  return (
    <>
      {tab === "videos" && <VideoList {...props} />}
      {tab === "playlists" && <PlaylistOptions {...props} />}
      {tab === "backgrounds" && <BackgroundOptions {...props} />}
      {count === 0 && <p className="live-empty">{t("mobileRemote.noResults")}</p>}
    </>
  );
}
