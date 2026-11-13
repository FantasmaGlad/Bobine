"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useHoverSound } from "@/lib/useHoverSound";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";
import { useKioskRemote, moveDomFocus, moveDomFocus2D, activateDomFocus } from "@/lib/useKioskRemote";
import Icon from "@/components/Icon";
import CinemaRow from "@/components/cinema/CinemaRow";
import CinemaAllList from "@/components/cinema/CinemaAllList";
import { thumbnailUrl, type CinemaVideo } from "@/lib/cinemaCatalog";
import { useFeatured, useProgramRows } from "@/components/cinema/useCinemaVideos";
import AppLogo from "@/components/AppLogo";
import CourseRatingWidget from "@/components/CourseRatingWidget";
import { getResolutionBadge, getAudioQualityBadge } from "@/lib/videoBadges";
import { getApiUrl } from "@/lib/apiUrl";
import { formatMinutes, formatWallClock } from "@/lib/format";
import GridRadioActive from "@/components/grid/GridRadioActive";
import GridStandby from "@/components/grid/GridStandby";
import NowPlayingCard from "@/components/grid/NowPlayingCard";
import { useNowPlaying } from "@/components/cinema/useNowPlaying";
import { useRatingPrompt } from "@/components/grid/useRatingPrompt";

export default function GridPage() {
  const { t, wiredDisplayMode, setWiredDisplayMode, waitTimeBetweenCourses } = useAppSettings();
  const [videos, setVideos] = useState<CinemaVideo[]>([]);
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const router = useRouter();

  const { state, sendCommand, displayOutputCable, cinemaState, libraryVersion } = usePlaybackSocket(undefined, undefined, "cable", undefined, "grid");

  useEffect(() => {
    if (state.state === "coach_mode") {
      router.replace("/coach");
    }
  }, [state.state, router]);
  const [launchWarning, setLaunchWarning] = useState<string | null>(null);
  const launchWarningTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const playHoverSound = useHoverSound("/sounds/survole.mp3");
  const themeFg = useThemeAccentForeground();

  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    const load = () => {
      fetch(getApiUrl("/videos?sort_by=title&order=asc"), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
        .then((data: CinemaVideo[]) => {
          if (cancelled || !Array.isArray(data)) return;
          setVideos((prev) => {
            const isSame =
              prev.length === data.length &&
              prev.every((v, i) => {
                const d = data[i];
                return (
                  d &&
                  v.id === d.id &&
                  v.title === d.title &&
                  v.program === d.program &&
                  v.release === d.release &&
                  v.duration_seconds === d.duration_seconds &&
                  v.thumbnail_path === d.thumbnail_path
                );
              });
            return isSame ? prev : data;
          });
        })
        .catch(() => {
          if (cancelled) return;
          if (retryTimer) clearTimeout(retryTimer);
          retryTimer = setTimeout(load, 3000);
        });
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [libraryVersion]);

  const lastLaunchRef = useRef<number>(0);
  const handleSelect = useCallback((video: CinemaVideo) => {
    const now = Date.now();
    if (now - lastLaunchRef.current < 1500) {
      return;
    }
    lastLaunchRef.current = now;
    sendCommand("cinema_command", {
      action: "launch",
      video_id: video.id,
      title: video.title,
      duration_seconds: video.duration_seconds,
    });
    if (displayOutputCable !== null && displayOutputCable !== "cinema") {
      setLaunchWarning(t("cinema.gridNoScreen"));
      if (launchWarningTimerRef.current) clearTimeout(launchWarningTimerRef.current);
      launchWarningTimerRef.current = setTimeout(() => setLaunchWarning(null), 6000);
    }
  }, [sendCommand, displayOutputCable, t]);

  useEffect(() => {
    return () => {
      if (launchWarningTimerRef.current) clearTimeout(launchWarningTimerRef.current);
    };
  }, []);

  const {
    nowPlaying, playPause: handleNowPlayingPlayPause, seekDelta: handleNowPlayingSeekDelta, commitSeek, stop: handleNowPlayingStop,
  } = useNowPlaying(cinemaState, sendCommand, true);

  const [ratingCourse, setRatingCourse] = useRatingPrompt(nowPlaying);

  const featured = useFeatured(videos);
  const featuredThumb = featured ? thumbnailUrl(featured) : null;

  const rows = useProgramRows(videos, t("cinema.otherProgram"));

  useKioskRemote(() => {
    if (wiredDisplayMode === "headless") {
      return {
        onLeft: () => moveDomFocus(".grid-standby-actions button, .grid-standby-actions a", -1),
        onRight: () => moveDomFocus(".grid-standby-actions button, .grid-standby-actions a", 1),
        onUp: () => moveDomFocus(".grid-standby-actions button, .grid-standby-actions a", -1),
        onDown: () => moveDomFocus(".grid-standby-actions button, .grid-standby-actions a", 1),
        onEnter: () => activateDomFocus(".grid-standby-actions button, .grid-standby-actions a"),
        onPlayPause: handleNowPlayingPlayPause,
      };
    }
    return {
      onLeft: () => moveDomFocus2D(".cinema-card, .cinema-hero-play", "left"),
      onRight: () => moveDomFocus2D(".cinema-card, .cinema-hero-play", "right"),
      onUp: () => moveDomFocus2D(".cinema-card, .cinema-hero-play", "up"),
      onDown: () => moveDomFocus2D(".cinema-card, .cinema-hero-play", "down"),
      onPrev: () => (nowPlaying ? handleNowPlayingSeekDelta(-30) : moveDomFocus2D(".cinema-card, .cinema-hero-play", "left")),
      onNext: () => (nowPlaying ? handleNowPlayingSeekDelta(30) : moveDomFocus2D(".cinema-card, .cinema-hero-play", "right")),
      onEnter: () => activateDomFocus(".cinema-card, .cinema-hero-play"),
      onPlayPause: () => {
        if (nowPlaying) {
          handleNowPlayingPlayPause();
        } else {
          activateDomFocus(".cinema-card, .cinema-hero-play");
        }
      },
      onBack: () => {
        if (nowPlaying) {
          handleNowPlayingStop();
        }
      },
    };
  });

  if (wiredDisplayMode === "headless") {
    return <GridStandby t={t} now={now} nowPlaying={nowPlaying} themeFg={themeFg} onSwitchToDual={() => setWiredDisplayMode("dual_screen")} />;
  }

  if (displayOutputCable === "radio") {
    return <GridRadioActive t={t} now={now} />;
  }

  return (
    <div className="cinema-root">
      {launchWarning && <div className="grid-launch-warning">{launchWarning}</div>}
      {videos.length === 0 && (
        <div className="cinema-empty-screen">
          <AppLogo className="cinema-empty-logo" />
          <span className="cinema-empty-clock">{formatWallClock(now)}</span>
          <span className="cinema-empty-message">{t("cinema.empty")}</span>
        </div>
      )}

      <div className="cinema-layer cinema-grid-layer visible">
        {featured && (
          <section className="cinema-hero">
            {featuredThumb && (
              <div className="cinema-hero-backdrop-wrap">
                <img className="cinema-hero-backdrop" src={featuredThumb} alt="" />
              </div>
            )}
            <div className="cinema-hero-scrim" />
            <div className="cinema-hero-content">
              <div className="cinema-hero-brand-row">
                <AppLogo size={110} className="cinema-brand-logo" />
              </div>
              <h1 className="cinema-hero-title">{featured.title}</h1>
              <div className="cinema-hero-meta-row">
                {featured.program && (
                  <span className="cinema-hero-program-tag">{featured.program}</span>
                )}
                {featured.release && (
                  <span className="cinema-hero-year">{featured.release}</span>
                )}
                {featured.duration_seconds && (
                  <span className="cinema-hero-duration">{formatMinutes(featured.duration_seconds)}</span>
                )}
                {getResolutionBadge(featured.width, featured.height) && (
                  <span className="cinema-hero-badge-pill">
                    {getResolutionBadge(featured.width, featured.height)}
                  </span>
                )}
                {getAudioQualityBadge(featured.audio_channels, featured.audio_codec, undefined, t) && (
                  <span className="cinema-hero-badge-pill">
                    {getAudioQualityBadge(featured.audio_channels, featured.audio_codec, undefined, t)}
                  </span>
                )}
              </div>
              {featured.description && (
                <p className="cinema-hero-description">{featured.description}</p>
              )}
              <div className="cinema-hero-actions">
                <button className="cinema-hero-play" style={{ color: themeFg }} onClick={() => handleSelect(featured)}>
                  <Icon name="play_arrow" size={28} color={themeFg} filled />
                  {t("cinema.launchCourse")}
                </button>
              </div>
            </div>

            {ratingCourse ? (
              <CourseRatingWidget
                videoId={ratingCourse.videoId}
                courseTitle={ratingCourse.title}
                channel="cable"
                autoCloseSeconds={waitTimeBetweenCourses > 0 ? waitTimeBetweenCourses : 20}
                onClose={() => setRatingCourse(null)}
              />
            ) : nowPlaying ? (
              <NowPlayingCard
                t={t}
                nowPlaying={nowPlaying}
                handleNowPlayingStop={handleNowPlayingStop}
                handleNowPlayingPlayPause={handleNowPlayingPlayPause}
                handleNowPlayingSeekDelta={handleNowPlayingSeekDelta}
                commitSeek={commitSeek}
              />
            ) : null}
          </section>
        )}

        <div className="cinema-sections">
          {rows.length === 0 && videos.length > 0 && <p className="cinema-empty">{t("cinema.empty")}</p>}

          {rows.map(([programName, items], rowIndex) => (
            <CinemaRow
              key={programName}
              programName={programName}
              items={items}
              rowIndex={rowIndex}
              onSelect={handleSelect}
              onHover={playHoverSound}
              coursesCountLabel={t("cinema.coursesCount", { count: items.length })}
            />
          ))}

          {videos.length > 0 && (
            <section className="cinema-all">
              <h2>{t("cinema.allCourses")}</h2>
              <CinemaAllList videos={videos} onSelect={handleSelect} onHover={playHoverSound} />
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
