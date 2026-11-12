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
import AppLogo from "@/components/AppLogo";
import MarqueeText from "@/components/MarqueeText";
import CourseRatingWidget from "@/components/CourseRatingWidget";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import { getResolutionBadge, getAudioQualityBadge } from "@/lib/videoBadges";
import { getApiUrl } from "@/lib/apiUrl";
import { formatMinutes, formatTime, formatWallClock } from "@/lib/format";

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

  const [nowPlayingTick, setNowPlayingTick] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowPlayingTick(Date.now()), 250);
    return () => clearInterval(id);
  }, []);
  const cinemaReceivedAtRef = React.useRef(0);
  const [pendingPlaying, setPendingPlaying] = useState<boolean | null>(null);
  const [optimisticSeek, setOptimisticSeek] = useState<{ position: number; timestamp: number } | null>(null);
  const optimisticTimerRef = useRef<NodeJS.Timeout | null>(null);

  const smoothedPositionRef = useRef<number>(0);
  const lastTickTimeRef = useRef<number>(Date.now());

  useEffect(() => {
    cinemaReceivedAtRef.current = Date.now();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réaction à un rapport externe, le rapport redevient la vérité
    setPendingPlaying(null);
    setOptimisticSeek((current) => {
      if (!current) return null;
      const elapsed = (Date.now() - current.timestamp) / 1000;
      const expected = current.position + (cinemaState?.playing ? elapsed : 0);
      if (Math.abs((cinemaState?.position_seconds ?? 0) - expected) < 2.5 || elapsed > 1.2) {
        return null;
      }
      return current;
    });
  }, [cinemaState]);

  useEffect(() => {
    return () => {
      if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current);
    };
  }, []);

  const nowPlayingRaw =
    cinemaState && cinemaState.title && nowPlayingTick - cinemaReceivedAtRef.current < 8000 ? cinemaState : null;
  const isPlayingEffective = pendingPlaying ?? nowPlayingRaw?.playing ?? false;

  const rawPosition = optimisticSeek
    ? Math.min(
        nowPlayingRaw?.duration_seconds || Infinity,
        optimisticSeek.position +
          (isPlayingEffective ? Math.max(0, (nowPlayingTick - optimisticSeek.timestamp) / 1000) : 0),
      )
    : nowPlayingRaw
    ? Math.min(
        nowPlayingRaw.duration_seconds || Infinity,
        nowPlayingRaw.position_seconds +
          (nowPlayingRaw.playing ? Math.max(0, (nowPlayingTick - cinemaReceivedAtRef.current) / 1000) : 0),
      )
    : 0;

  const nowMs = Date.now();
  const dt = Math.max(0, Math.min(1.0, (nowMs - lastTickTimeRef.current) / 1000));
  lastTickTimeRef.current = nowMs;

  let computedPosition: number;
  if (!nowPlayingRaw) {
    smoothedPositionRef.current = 0;
    computedPosition = 0;
  } else if (optimisticSeek) {
    smoothedPositionRef.current = rawPosition;
    computedPosition = rawPosition;
  } else if (!isPlayingEffective) {
    smoothedPositionRef.current = nowPlayingRaw.position_seconds;
    computedPosition = nowPlayingRaw.position_seconds;
  } else {
    const expected = smoothedPositionRef.current + dt;
    if (Math.abs(expected - rawPosition) >= 2.5) {
      smoothedPositionRef.current = rawPosition;
    } else {
      smoothedPositionRef.current = Math.max(expected, rawPosition - 0.5);
    }
    const duration = nowPlayingRaw.duration_seconds || Infinity;
    computedPosition = Math.min(duration, smoothedPositionRef.current);
  }

  const nowPlaying = nowPlayingRaw
    ? {
        ...nowPlayingRaw,
        playing: isPlayingEffective,
        position_seconds: computedPosition,
      }
    : null;
  const [nowPlayingSeekDrag, setNowPlayingSeekDrag] = useState<number | null>(null);

  const handleNowPlayingPlayPause = useCallback(() => {
    if (!nowPlaying) return;
    const next = !nowPlaying.playing;
    setPendingPlaying(next);
    sendCommand("cinema_command", { action: next ? "play" : "pause" });
  }, [nowPlaying, sendCommand]);

  const handleNowPlayingSeekDelta = useCallback((delta: number) => {
    if (!nowPlaying) return;
    const currentBase = optimisticSeek ? optimisticSeek.position : nowPlaying.position_seconds;
    const target = Math.max(0, Math.min(currentBase + delta, nowPlaying.duration_seconds || Infinity));
    const now = Date.now();
    setOptimisticSeek({ position: target, timestamp: now });
    if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current);
    optimisticTimerRef.current = setTimeout(() => {
      setOptimisticSeek(null);
    }, 2000);
    sendCommand("cinema_command", { action: "seek", position_seconds: target });
  }, [nowPlaying, optimisticSeek, sendCommand]);

  const handleNowPlayingStop = useCallback(() => {
    sendCommand("cinema_command", { action: "stop" });
  }, [sendCommand]);

  const [ratingCourse, setRatingCourse] = useState<{
    videoId: number;
    title: string;
  } | null>(null);
  const ratingShownForVideoRef = useRef<number | null>(null);
  const lastPlayingRef = useRef<{
    videoId: number;
    title: string;
    position: number;
    duration: number;
  } | null>(null);

  useEffect(() => {
    if (nowPlaying && nowPlaying.video_id) {
      lastPlayingRef.current = {
        videoId: nowPlaying.video_id,
        title: nowPlaying.title || "",
        position: nowPlaying.position_seconds,
        duration: nowPlaying.duration_seconds,
      };

      if (
        nowPlaying.duration_seconds > 0 &&
        nowPlaying.position_seconds / nowPlaying.duration_seconds >= 0.95 &&
        ratingShownForVideoRef.current !== nowPlaying.video_id
      ) {
        ratingShownForVideoRef.current = nowPlaying.video_id;
        setRatingCourse({
          videoId: nowPlaying.video_id,
          title: nowPlaying.title || "",
        });
      }
    } else if (!nowPlaying && lastPlayingRef.current) {
      const last = lastPlayingRef.current;
      if (
        last.duration > 0 &&
        last.position / last.duration >= 0.90 &&
        ratingShownForVideoRef.current !== last.videoId
      ) {
        ratingShownForVideoRef.current = last.videoId;
        setRatingCourse({
          videoId: last.videoId,
          title: last.title,
        });
      }
      lastPlayingRef.current = null;
    }
  }, [nowPlaying]);

  const [scrambleTick, setScrambleTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setScrambleTick((v) => v + 1), 60_000);
    return () => clearInterval(id);
  }, []);
  const SCRAMBLE_INTERVAL_MS = 15 * 60 * 1000;
  const featured = React.useMemo(() => {
    if (videos.length === 0) return null;
    const bucket = Math.floor(Date.now() / SCRAMBLE_INTERVAL_MS);
    const hash = Math.abs((bucket * 2654435761) % videos.length);
    return videos[hash];
    // eslint-disable-next-line react-hooks/exhaustive-deps -- scrambleTick ne sert qu'à forcer le recalcul périodique
  }, [videos, scrambleTick]);
  const featuredThumb = featured ? thumbnailUrl(featured) : null;

  const rows = React.useMemo(() => {
    const byProgram = new Map<string, CinemaVideo[]>();
    for (const v of videos) {
      const key = v.program || t("cinema.otherProgram");
      if (!byProgram.has(key)) byProgram.set(key, []);
      byProgram.get(key)!.push(v);
    }
    return [...byProgram.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [videos, t]);

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
    return (
      <div className="grid-standby-root">
        <div className="grid-standby-card">
          <div className="grid-standby-header">
            <AppLogo size={48} className="grid-standby-logo" />
            <span className="grid-standby-clock">{formatWallClock(now)}</span>
          </div>

          <div className="grid-standby-content">
            <h1 className="grid-standby-title">{t("settingsPage.gridStandbyTitle")}</h1>
            <p className="grid-standby-subtitle">{t("settingsPage.gridStandbySubtitle")}</p>

            <div className="grid-standby-status-box">
              <div className="grid-standby-status-badge">
                <span className="grid-standby-pulse-dot" />
                <Icon name="tv" size={20} />
                <span>{t("settingsPage.gridStandbyHdmiActive")}</span>
              </div>
              <p className="grid-standby-status-desc">{t("settingsPage.gridStandbyHdmiHelp")}</p>
              {nowPlaying && (
                <div className="grid-standby-now-playing">
                  <span className="grid-standby-now-playing-label">{t("cinema.nowPlaying")} :</span>
                  <strong className="grid-standby-now-playing-title">{nowPlaying.title}</strong>
                  {nowPlaying.duration_seconds ? (
                    <span className="grid-standby-now-playing-time">
                      ({formatTime(nowPlaying.position_seconds)} / {formatTime(nowPlaying.duration_seconds)})
                    </span>
                  ) : null}
                </div>
              )}
            </div>

            <div className="grid-standby-actions">
              <button
                type="button"
                className="btn btn-primary grid-standby-btn-main"
                style={{ color: themeFg }}
                onClick={() => setWiredDisplayMode("dual_screen")}
              >
                <Icon name="devices" size={22} color={themeFg} />
                <span>{t("settingsPage.gridStandbySwitchToDual")}</span>
              </button>
              <p className="grid-standby-action-hint">{t("settingsPage.gridStandbySwitchToDualHelp")}</p>

              <a
                href="/"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary grid-standby-btn-admin"
              >
                <Icon name="settings" size={18} />
                <span>{t("settingsPage.gridStandbyOpenAdmin")}</span>
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (displayOutputCable === "radio") {
    return (
      <div className="grid-standby-root" style={{ overflowY: "auto", alignItems: "flex-start" }}>
        <div className="dashboard-container" style={{ width: "100%", maxWidth: "920px", margin: "0 auto", padding: "20px" }}>
          <div className="live-block" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
            <AppLogo size={40} className="grid-standby-logo" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <h3 style={{ margin: 0 }}>
                <Icon name="radio" size={18} /> {t("radioRemote.gridRadioActiveTitle")}
              </h3>
              <p style={{ margin: "4px 0 0", color: "var(--text-muted)", fontSize: "0.85rem" }}>
                {t("radioRemote.gridRadioActiveHint")}
              </p>
            </div>
            <span className="grid-standby-clock">{formatWallClock(now)}</span>
          </div>
          <RadioRemotePanel key="radio_cable" channel="radio_cable" variant="compact" />
        </div>
      </div>
    );
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
                {/* eslint-disable-next-line @next/next/no-img-element */}
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
              <section className="grid-now-playing">
                <button
                  className="grid-now-playing-close"
                  onClick={handleNowPlayingStop}
                  title={t("cinema.removeCourse")}
                  aria-label={t("cinema.removeCourse")}
                >
                  <Icon name="close" size={18} />
                </button>
                <span className="grid-now-playing-label">{t("cinema.nowPlaying")}</span>
                <MarqueeText text={nowPlaying.title} className="grid-now-playing-title" />
                <input
                  type="range"
                  className="grid-now-playing-seek"
                  min={0}
                  max={nowPlaying.duration_seconds || 0}
                  step={1}
                  value={nowPlayingSeekDrag ?? nowPlaying.position_seconds}
                  onChange={(e) => setNowPlayingSeekDrag(Number(e.target.value))}
                  onMouseUp={(e) => {
                    const value = Number((e.target as HTMLInputElement).value);
                    const now = Date.now();
                    setOptimisticSeek({ position: value, timestamp: now });
                    if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current);
                    optimisticTimerRef.current = setTimeout(() => setOptimisticSeek(null), 2000);
                    sendCommand("cinema_command", { action: "seek", position_seconds: value });
                    setNowPlayingSeekDrag(null);
                  }}
                  onTouchEnd={(e) => {
                    const value = Number((e.target as HTMLInputElement).value);
                    const now = Date.now();
                    setOptimisticSeek({ position: value, timestamp: now });
                    if (optimisticTimerRef.current) clearTimeout(optimisticTimerRef.current);
                    optimisticTimerRef.current = setTimeout(() => setOptimisticSeek(null), 2000);
                    sendCommand("cinema_command", { action: "seek", position_seconds: value });
                    setNowPlayingSeekDrag(null);
                  }}
                />
                <div className="grid-now-playing-times">
                  <span>{formatTime(nowPlayingSeekDrag ?? nowPlaying.position_seconds)}</span>
                  <span>{formatTime(nowPlaying.duration_seconds)}</span>
                </div>
                <div className="grid-now-playing-controls">
                  <button
                    className="grid-now-playing-btn"
                    onClick={() => handleNowPlayingSeekDelta(-10)}
                    title={t("cinema.seekBack")}
                    aria-label={t("cinema.seekBack")}
                  >
                    <Icon name="replay_10" size={26} />
                  </button>
                  <button
                    className="grid-now-playing-btn grid-now-playing-btn-main"
                    onClick={handleNowPlayingPlayPause}
                    title={nowPlaying.playing ? t("cinema.pause") : t("cinema.play")}
                  >
                    <Icon name={nowPlaying.playing ? "pause" : "play_arrow"} size={30} filled />
                  </button>
                  <button
                    className="grid-now-playing-btn"
                    onClick={() => handleNowPlayingSeekDelta(10)}
                    title={t("cinema.seekForward")}
                    aria-label={t("cinema.seekForward")}
                  >
                    <Icon name="forward_10" size={26} />
                  </button>
                </div>
              </section>
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
