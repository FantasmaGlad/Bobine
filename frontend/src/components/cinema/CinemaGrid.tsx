"use client";

import CinemaAllList from "@/components/cinema/CinemaAllList";
import CinemaRow from "@/components/cinema/CinemaRow";
import { useAppSettings } from "@/lib/AppSettingsContext";
import type { CinemaVideo } from "@/lib/cinemaCatalog";
import { useHoverSound } from "@/lib/useHoverSound";

import CinemaHero, { useHeroScroll } from "./CinemaHero";
import NowPlayingPanel from "./NowPlayingPanel";
import { useFeatured, useProgramRows } from "./useCinemaVideos";
import type { NowPlaying } from "./useNowPlaying";

interface Props {
  visible: boolean;
  videos: CinemaVideo[];
  remote: NowPlaying;
  onSelect: (video: CinemaVideo) => void;
}

export default function CinemaGrid({ visible, videos, remote, onSelect }: Props) {
  const { t } = useAppSettings();
  const hero = useHeroScroll();
  const featured = useFeatured(videos);
  const rows = useProgramRows(videos, t("cinema.otherProgram"));
  const playHoverSound = useHoverSound("/sounds/survole.mp3");
  return (
    <div className={`cinema-layer cinema-grid-layer ${visible ? "visible" : ""}`} onScroll={hero.onScroll}>
      {featured && (
        <CinemaHero featured={featured} scrolled={hero.scrolled} onSelect={onSelect}>
          {remote.nowPlaying && <NowPlayingPanel remote={remote} />}
        </CinemaHero>
      )}
      <div className="cinema-sections">
        {rows.length === 0 && <p className="cinema-empty">{t("cinema.empty")}</p>}
        {rows.map(([programName, items], rowIndex) => (
          <CinemaRow key={programName} programName={programName} items={items} rowIndex={rowIndex} onSelect={onSelect} onHover={playHoverSound}
            coursesCountLabel={t("cinema.coursesCount", { count: items.length })} accentTitle />
        ))}
        {videos.length > 0 && (
          <section className="cinema-all">
            <h2>{t("cinema.allCourses")}</h2>
            <CinemaAllList videos={videos} onSelect={onSelect} onHover={playHoverSound} />
          </section>
        )}
      </div>
    </div>
  );
}
