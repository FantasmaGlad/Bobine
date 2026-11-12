"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import { useMediaSound } from "@/lib/useMediaSound";
import { videoStreamUrl } from "@/lib/clientCodecSupport";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { buildOutputUrl } from "@/lib/displayChannel";
import type { ClockAnchor } from "@/lib/playbackClock";
import { useMediaClockFollower, type ClockTarget } from "@/lib/useMediaClockFollower";
import type { CinemaCommandExtra } from "@/lib/usePlaybackSocket";
import { getDisplayChannel, isWiredDisplay, useDisplayOutputRedirect } from "@/lib/useDisplayOutputRedirect";
import { useHoverSound } from "@/lib/useHoverSound";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";
import { useKioskRemote, moveDomFocus2D, activateDomFocus, selectRemoteTarget } from "@/lib/useKioskRemote";
import { adjustMediaVolume, useVolumeHud, VOLUME_STEP } from "@/lib/volumeHud";
import Icon from "@/components/Icon";
import CinemaRow from "@/components/cinema/CinemaRow";
import CinemaAllList from "@/components/cinema/CinemaAllList";
import { thumbnailUrl, type CinemaVideo } from "@/lib/cinemaCatalog";
import AppLogo from "@/components/AppLogo";
import CourseRatingWidget from "@/components/CourseRatingWidget";
import { getResolutionBadge, getAudioQualityBadge } from "@/lib/videoBadges";
import { formatCleanDescription } from "@/lib/formatDescription";
import { subtitleSrc, useApplySubtitleMode, useVideoSubtitles } from "@/lib/subtitles";
import { chapterJumpTarget, useVideoChapters } from "@/lib/chapters";
import ChapterTicks from "@/components/ChapterTicks";
import ChapterToast from "@/components/ChapterToast";
import VolumeOsd from "@/components/VolumeOsd";
import { getApiUrl } from "@/lib/apiUrl";
import { formatMinutes, formatTime, formatWallClock } from "@/lib/format";
import { unloadMedia } from "@/lib/mediaElement";

const CINEMA_GRID_CARDS =
  ".cinema-grid-layer .cinema-hero-play, .cinema-grid-layer .cinema-card, .cinema-grid-layer .cinema-all-item";

function seekWhenReady(el: HTMLMediaElement, targetSeconds: number, onDone?: () => void) {
  const apply = () => {
    try {
      const wasPlaying = !el.paused;
      if (wasPlaying) el.pause();
      el.currentTime = targetSeconds;
      if (wasPlaying) {
        el.addEventListener(
          "seeked",
          () => {
            el.play().catch(() => {});
            onDone?.();
          },
          { once: true }
        );
      } else {
        if (el.paused && wasPlaying) el.play().catch(() => {});
        onDone?.();
      }
    } catch {
    }
  };
  if (el.readyState >= HTMLMediaElement.HAVE_METADATA) apply();
  else el.addEventListener("loadedmetadata", apply, { once: true });
}

const CONTROLS_HIDE_MS = 3000;
const UP_NEXT_AUTOPLAY_SECONDS = 5 * 60;
const SCRAMBLE_INTERVAL_MS = 15 * 60 * 1000;

type Phase = "grid" | "playing" | "ended";

interface CinemaSync {
  anchor: ClockAnchor;
  videoId: number;
}

function selectCinemaTarget(sync: CinemaSync | null): ClockTarget {
  if (!sync) return { anchor: null, mode: null };
  return { anchor: sync.anchor, mode: sync.anchor.running ? "playing" : "paused", key: sync.videoId };
}

export default function CinemaPage() {
  const { t, wiredDisplayMode, waitTimeBetweenCourses } = useAppSettings();
  const deckARef = useRef<HTMLVideoElement | null>(null);
  const deckBRef = useRef<HTMLVideoElement | null>(null);
  const [activeDeck, setActiveDeck] = useState<"A" | "B">("A");
  const activeDeckRef = useRef<"A" | "B">("A");
  activeDeckRef.current = activeDeck;
  const videoRef = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    videoRef.current = activeDeck === "A" ? deckARef.current : deckBRef.current;
  }, [activeDeck]);

  const [volumeHud, showVolumeHud] = useVolumeHud();
  const [endedVideo, setEndedVideo] = useState<CinemaVideo | null>(null);
  const [videos, setVideos] = useState<CinemaVideo[]>([]);
  const [phase, setPhase] = useState<Phase>("grid");
  const [selected, setSelected] = useState<CinemaVideo | null>(null);

  const [activeSubtitleId, setActiveSubtitleId] = useState<number | "off">("off");
  const [showSubtitleMenu, setShowSubtitleMenu] = useState<boolean>(false);
  const subtitles = useVideoSubtitles(selected?.id, getApiUrl);
  useApplySubtitleMode([deckARef, deckBRef], subtitles, activeSubtitleId);
  const chapters = useVideoChapters(selected?.id, getApiUrl);
  const [heroScrolled, setHeroScrolled] = useState(false);

  useEffect(() => {
    setActiveSubtitleId("off");
  }, [selected?.id]);

  const selectSubtitleTrack = useCallback((subId: number | "off") => {
    setActiveSubtitleId(subId);
  }, []);

  const hideControls = wiredDisplayMode === "dual_screen" && isWiredDisplay();
  const [userStandbyMode, setUserStandbyMode] = useState(false);
  const effectiveHideControls = hideControls || userStandbyMode;

  const [now, setNow] = useState<Date>(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const [isPlaying, setIsPlaying] = useState(false);
  const [needsTapToPlay, setNeedsTapToPlay] = useState(false);
  const [position, setPosition] = useState(0);
  const lastPositionUpdateRef = useRef(0);
  const lastSeekTimeRef = useRef(0);
  const [controlsVisible, setControlsVisible] = useState(true);
  const controlsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const deckUnloadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wakeControls = useCallback(() => {
    setControlsVisible(true);
    if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current);
    controlsTimerRef.current = setTimeout(() => setControlsVisible(false), CONTROLS_HIDE_MS);
  }, []);
  const [seekDragValue, setSeekDragValue] = useState<number | null>(null);
  const [upNext, setUpNext] = useState<CinemaVideo | null>(null);
  const [upNextRemaining, setUpNextRemaining] = useState(UP_NEXT_AUTOPLAY_SECONDS);
  const upNextTaskRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [channel] = useState<"cable" | "network">(() => getDisplayChannel("cinema"));
  const cinemaCmdRef = useRef<((action: string, positionSeconds: number, videoId?: number, extra?: CinemaCommandExtra) => void) | null>(null);
  const [cinemaSync, setCinemaSync] = useState<CinemaSync | null>(null);
  const { state, displayOutputCable, displayOutputNetwork, sendCommand, cinemaState, libraryVersion, serverNow } = usePlaybackSocket(
    undefined,
    undefined,
    channel,
    (action, positionSeconds, videoId, extra) => cinemaCmdRef.current?.(action, positionSeconds, videoId, extra),
    "cinema",
  );
  useMediaSound(deckARef, state.sound);
  useMediaSound(deckBRef, state.sound);
  useDisplayOutputRedirect("cinema", displayOutputCable, displayOutputNetwork);

  useEffect(() => {
    if (state.state === "coach_mode") {
      window.location.replace(buildOutputUrl("kiosk", window.location.search, channel));
    }
  }, [state.state, channel]);
  const playHoverSound = useHoverSound("/sounds/survole.mp3");

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

  useEffect(() => {
    if (selected && (!selected.thumbnail_path || !selected.description)) {
      const fresh = videos.find((v) => Number(v.id) === Number(selected.id));
      if (fresh) {
        setSelected((prev) => (prev ? { ...prev, ...fresh } : fresh));
      }
    }
  }, [videos, selected]);

  const clearUpNextTask = () => {
    if (upNextTaskRef.current) clearInterval(upNextTaskRef.current);
    upNextTaskRef.current = null;
  };

  const startPlayback = useCallback((video: CinemaVideo) => {
    const currentActive = activeDeckRef.current === "A" ? deckARef.current : deckBRef.current;
    const idle = activeDeckRef.current === "A" ? deckBRef.current : deckARef.current;

    setNeedsTapToPlay(false);
    wakeControls();

    if (!isPlaying || !idle || !currentActive) {
      const target = currentActive || idle;
      if (!target) return;
      target.src = videoStreamUrl(getApiUrl, video.id);
      target.currentTime = 0;
      target.volume = 1.0;
      target.muted = false;
      target.load();
      target.play()
        .then(() => setIsPlaying(true))
        .catch(() => {
          setIsPlaying(false);
          setNeedsTapToPlay(true);
        });
      return;
    }

    if (deckUnloadTimerRef.current) {
      clearTimeout(deckUnloadTimerRef.current);
      deckUnloadTimerRef.current = null;
    }

    idle.src = videoStreamUrl(getApiUrl, video.id);
    idle.currentTime = 0;
    idle.volume = 1.0;
    idle.muted = false;
    idle.load();

    const onCanPlay = () => {
      idle.removeEventListener("canplay", onCanPlay);
      idle.play()
        .then(() => {
          setIsPlaying(true);
          const nextDeck = activeDeckRef.current === "A" ? "B" : "A";
          setActiveDeck(nextDeck);
          if (videoRef.current) videoRef.current = idle;

          deckUnloadTimerRef.current = setTimeout(() => {
            deckUnloadTimerRef.current = null;
            unloadMedia(currentActive);
          }, 450);
        })
        .catch(() => {
          setIsPlaying(false);
          setNeedsTapToPlay(true);
        });
    };

    idle.addEventListener("canplay", onCanPlay, { once: true });
  }, [isPlaying, wakeControls]);

  const handleSelect = useCallback(
    (video: CinemaVideo) => {
      setCinemaSync(null);
      clearUpNextTask();
      setUpNext(null);
      setEndedVideo(null);
      setSelected(video);
      setPhase("playing");
      setPosition(0);
      startPlayback(video);
    },
    [startPlayback],
  );

  const playImmediately = handleSelect;

  const handleBackToMenu = useCallback(() => {
    setCinemaSync(null);
    clearUpNextTask();
    unloadMedia(deckARef.current);
    unloadMedia(deckBRef.current);
    setPhase("grid");
    setSelected(null);
    setUpNext(null);
    setEndedVideo(null);
    setIsPlaying(false);
    setNeedsTapToPlay(false);
    setPosition(0);
  }, []);

  const [nowPlayingTick, setNowPlayingTick] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowPlayingTick(Date.now()), 250);
    return () => clearInterval(id);
  }, []);
  const cinemaReceivedAtRef = React.useRef(0);
  const [pendingPlaying, setPendingPlaying] = useState<boolean | null>(null);
  const [optimisticSeek, setOptimisticSeek] = useState<{ position: number; timestamp: number } | null>(null);

  useEffect(() => {
    cinemaReceivedAtRef.current = Date.now();
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

  const nowPlayingRaw =
    cinemaState && cinemaState.title && nowPlayingTick - cinemaReceivedAtRef.current < 8000 ? cinemaState : null;
  const isPlayingEffective = pendingPlaying ?? nowPlayingRaw?.playing ?? false;
  const computedPosition = optimisticSeek
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
    setOptimisticSeek({ position: target, timestamp: Date.now() });
    sendCommand("cinema_command", { action: "seek", position_seconds: target });
  }, [nowPlaying, optimisticSeek, sendCommand]);

  const handleEnded = useCallback(() => {
    setCinemaSync(null);
    const el = activeDeckRef.current === "A" ? deckARef.current : deckBRef.current;
    if (el) {
      el.pause();
    }
    setIsPlaying(false);
    if (selected) {
      setEndedVideo(selected);
    }
    const candidates = videos.filter((v) => v.id !== selected?.id);
    if (candidates.length === 0) {
      handleBackToMenu();
      return;
    }
    const next = candidates[Math.floor(Math.random() * candidates.length)];
    setUpNext(next);
    setUpNextRemaining(UP_NEXT_AUTOPLAY_SECONDS);
    setPhase("ended");
    clearUpNextTask();
    upNextTaskRef.current = setInterval(() => {
      setUpNextRemaining((prev) => {
        if (prev <= 1) {
          clearUpNextTask();
          playImmediately(next);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [videos, selected, handleBackToMenu, playImmediately]);

  useEffect(() => {
    const deckA = deckARef;
    const deckB = deckBRef;
    return () => {
      clearUpNextTask();
      if (deckUnloadTimerRef.current) clearTimeout(deckUnloadTimerRef.current);
      if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current);
      unloadMedia(deckA.current);
      unloadMedia(deckB.current);
    };
  }, []);

  const handlePlayPause = () => {
    const el = videoRef.current;
    if (!el) return;
    setCinemaSync(null);
    if (needsTapToPlay) {
      el.play().then(() => { setIsPlaying(true); setNeedsTapToPlay(false); }).catch(() => {});
      return;
    }
    if (el.paused) {
      el.play().then(() => setIsPlaying(true)).catch(() => {});
    } else {
      el.pause();
      setIsPlaying(false);
    }
  };

  const jumpChapter = (direction: "next" | "prev") => {
    const el = videoRef.current;
    if (!el) return;
    const target = chapterJumpTarget(chapters, el.currentTime || 0, direction);
    if (target !== null) seekBy(target - (el.currentTime || 0));
  };

  const seekBy = (delta: number) => {
    const el = videoRef.current;
    if (!el) return;
    setCinemaSync(null);
    const target = Math.max(0, Math.min((el.currentTime || 0) + delta, el.duration || 0));
    el.currentTime = target;
    setPosition(target);
    wakeControls();
  };
  const changeLocalVolume = useCallback((delta: number, toggleMute = false) => {
    showVolumeHud(adjustMediaVolume([deckARef.current, deckBRef.current], delta, toggleMute));
    wakeControls();
  }, [showVolumeHud, wakeControls]);

  const focusHero = () => {
    document.querySelector<HTMLElement>(".cinema-grid-layer")?.scrollTo({ top: 0, behavior: "smooth" });
    const items = Array.from(document.querySelectorAll<HTMLElement>(CINEMA_GRID_CARDS));
    const hero = items.find((el) => el.classList.contains("cinema-hero-play"));
    if (hero) selectRemoteTarget(items, hero);
  };
  const volumeKeys = {
    onVolumeUp: () => changeLocalVolume(VOLUME_STEP),
    onVolumeDown: () => changeLocalVolume(-VOLUME_STEP),
    onMute: () => changeLocalVolume(0, true),
  };

  useKioskRemote(() => {
    if (phase === "grid") {
      if (userStandbyMode) {
        const exitStandby = () => {
          setUserStandbyMode(false);
          setTimeout(focusHero, 50);
        };
        return {
          ...volumeKeys,
          onEnter: exitStandby,
          onPlayPause: exitStandby,
          onLeft: exitStandby,
          onRight: exitStandby,
          onUp: exitStandby,
          onDown: exitStandby,
          onBack: exitStandby,
        };
      }
      return {
        ...volumeKeys,
        onLeft: () => moveDomFocus2D(CINEMA_GRID_CARDS, "left"),
        onRight: () => moveDomFocus2D(CINEMA_GRID_CARDS, "right"),
        onUp: () => moveDomFocus2D(CINEMA_GRID_CARDS, "up"),
        onDown: () => moveDomFocus2D(CINEMA_GRID_CARDS, "down"),
        onPrev: () => moveDomFocus2D(CINEMA_GRID_CARDS, "left"),
        onNext: () => moveDomFocus2D(CINEMA_GRID_CARDS, "right"),
        onEnter: () => activateDomFocus(CINEMA_GRID_CARDS),
        onPlayPause: () => activateDomFocus(CINEMA_GRID_CARDS),
        onBack: () => {
          if ((document.querySelector<HTMLElement>(".cinema-grid-layer")?.scrollTop ?? 0) > 0) focusHero();
          else setUserStandbyMode(true);
        },
      };
    }
    if (phase === "playing") {
      return {
        ...volumeKeys,
        onEnter: handlePlayPause,
        onPlayPause: handlePlayPause,
        onBack: handleBackToMenu,
        onLeft: () => seekBy(-10),
        onRight: () => seekBy(10),
        onUp: volumeKeys.onVolumeUp,
        onDown: volumeKeys.onVolumeDown,
        onPrev: () => seekBy(-30),
        onNext: () => seekBy(30),
        onChapterNext: () => jumpChapter("next"),
        onChapterPrev: () => jumpChapter("prev"),
      };
    }
    if (phase === "ended") {
      return {
        ...volumeKeys,
        onEnter: () => { if (upNext) playImmediately(upNext); },
        onPlayPause: () => { if (upNext) playImmediately(upNext); },
        onBack: handleBackToMenu,
      };
    }
    return volumeKeys;
  });

  useEffect(() => {
    cinemaCmdRef.current = (action, positionSeconds, videoId, extra) => {
      const el = videoRef.current;
      if (action === "stop") {
        handleBackToMenu();
        return;
      }
      if (action === "launch") {
        let video = videos.find((v) => Number(v.id) === Number(videoId));
        if (!video && videoId) {
          video = {
            id: Number(videoId),
            title: extra?.title || "",
            program: null,
            release: null,
            duration_seconds: extra?.duration_seconds ?? null,
            thumbnail_path: null,
          };
        }
        if (video) {
          handleSelect(video);
          if (extra?.clock && extra.clock_video_id === Number(video.id)) {
            setCinemaSync({ anchor: extra.clock, videoId: extra.clock_video_id });
          }
        }
        return;
      }
      if (!el || phase !== "playing") return;
      if (action === "pause") {
        el.pause();
        setIsPlaying(false);
      } else if (action === "play") {
        el.play().then(() => setIsPlaying(true)).catch(() => {});
      } else if (action === "seek") {
        lastSeekTimeRef.current = Date.now();
        seekWhenReady(el, positionSeconds, () => setPosition(positionSeconds));
      }
      if (extra?.clock && extra.clock_video_id !== undefined && Number(selected?.id) === extra.clock_video_id) {
        setCinemaSync({ anchor: extra.clock, videoId: extra.clock_video_id });
      }
    };
  }, [phase, handleBackToMenu, videos, handleSelect, selected?.id]);

  const cinemaMediaRef = useMemo(() => ({ get current() { return videoRef.current; } }), []);
  useMediaClockFollower({
    mediaRef: cinemaMediaRef,
    state: cinemaSync,
    select: selectCinemaTarget,
    isMediaForKey: (el, key) => el.src.includes(`/videos/${key}/stream`),
    serverNow,
    tryPlay: (el) => {
      el?.play().catch(() => {});
    },
    onSeek: () => {
      lastSeekTimeRef.current = Date.now();
    },
  });

  useEffect(() => {
    let lastTime = -1;
    let stallCount = 0;

    const interval = window.setInterval(() => {
      const video = videoRef.current;
      if (!video || video.paused || video.seeking || video.ended || !video.src) {
        lastTime = -1;
        stallCount = 0;
        return;
      }
      if (Date.now() - lastSeekTimeRef.current < 3500) {
        lastTime = video.currentTime;
        stallCount = 0;
        return;
      }

      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        if (Math.abs(video.currentTime - lastTime) < 0.05) {
          stallCount++;
          if (stallCount >= 3) {
            stallCount = 0;
            video.play().catch(() => {});
          }
        } else {
          stallCount = 0;
        }
      }
      lastTime = video.currentTime;
    }, 2500);

    return () => window.clearInterval(interval);
  }, []);

  const reportNowRef = useRef<(() => void) | null>(null);
  useEffect(() => {
    if (phase !== "playing") {
      reportNowRef.current = null;
      sendCommand("cinema_report", { title: null, playing: false, position_seconds: 0, duration_seconds: 0 });
      return;
    }
    const report = () => {
      const el = videoRef.current;
      if (el?.seeking) return;
      sendCommand("cinema_report", {
        title: selected?.title ?? null,
        video_id: selected?.id ?? null,
        program: selected?.program ?? null,
        position_seconds: el?.currentTime ?? 0,
        duration_seconds: selected?.duration_seconds ?? el?.duration ?? 0,
        playing: el ? !el.paused : false,
      });
    };
    reportNowRef.current = report;
    report();
    const id = setInterval(report, 2000);
    return () => {
      reportNowRef.current = null;
      clearInterval(id);
    };
  }, [phase, selected, sendCommand]);

  const isPlayingLayer = phase === "playing";
  const isEnded = phase === "ended";
  const showGrid = phase === "grid";

  const programAccent = "var(--accent-primary)";
  const duration = selected?.duration_seconds ?? 0;
  const displayPosition = seekDragValue ?? position;

  const rows = React.useMemo(() => {
    const byProgram = new Map<string, CinemaVideo[]>();
    for (const v of videos) {
      const key = v.program || t("cinema.otherProgram");
      if (!byProgram.has(key)) byProgram.set(key, []);
      byProgram.get(key)!.push(v);
    }
    return [...byProgram.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [videos, t]);

  const [scrambleTick, setScrambleTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setScrambleTick((v) => v + 1), 60_000);
    return () => clearInterval(id);
  }, []);
  const featured = React.useMemo(() => {
    if (videos.length === 0) return null;
    const bucket = Math.floor(Date.now() / SCRAMBLE_INTERVAL_MS);
    const hash = Math.abs((bucket * 2654435761) % videos.length);
    return videos[hash];
    // eslint-disable-next-line react-hooks/exhaustive-deps -- scrambleTick ne sert qu'à forcer le recalcul périodique, Date.now() n'est pas une dépendance stable
  }, [videos, scrambleTick]);
  const featuredThumb = featured ? thumbnailUrl(featured) : null;

  const upNextThumb = upNext ? thumbnailUrl(upNext) : null;
  const upNextAccent = "var(--accent-primary)";
  const upNextProgressDeg = (1 - upNextRemaining / UP_NEXT_AUTOPLAY_SECONDS) * 360;

  const themeFg = useThemeAccentForeground();

  return (
    <div
      className="cinema-root"
      onMouseMove={isPlayingLayer ? wakeControls : undefined}
      onTouchStart={isPlayingLayer ? wakeControls : undefined}
      onPointerDown={isPlayingLayer ? wakeControls : undefined}
    >
      {videos.length === 0 && (
        <div className="cinema-empty-screen">
          <AppLogo className="cinema-empty-logo" />
          <span className="cinema-empty-clock" suppressHydrationWarning>{formatWallClock(now)}</span>
          <span className="cinema-empty-message">{t("cinema.empty")}</span>
        </div>
      )}

      {effectiveHideControls && showGrid && (
        <div className="cinema-standby-screen">
          <AppLogo size={96} className="cinema-standby-logo" />
          <span className="cinema-standby-clock" suppressHydrationWarning>{formatWallClock(now)}</span>
          <h1 className="cinema-standby-title">{t("cinema.standbyTitle")}</h1>
          <p className="cinema-standby-hint">{t("cinema.standbyHint")}</p>
        </div>
      )}

      {!effectiveHideControls && (
        <div
          className={`cinema-layer cinema-grid-layer ${showGrid ? "visible" : ""}`}
          onScroll={(e) => { if (!heroScrolled && e.currentTarget.scrollTop > 24) setHeroScrolled(true); }}
        >
          {featured && (
            <section className="cinema-hero" data-remote-scroll-top>
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
                  <p className="cinema-hero-description">{formatCleanDescription(featured.description)}</p>
                )}
                <div className="cinema-hero-actions">
                  <button className="cinema-hero-play" style={{ color: themeFg }} onClick={() => handleSelect(featured)}>
                    <Icon name="play_arrow" size={28} color={themeFg} filled />
                    {t("cinema.launchCourse")}
                  </button>
                </div>
              </div>
              <button
                type="button"
                className="cinema-scroll-hint"
                tabIndex={-1}
                hidden={heroScrolled}
                onClick={() => document.querySelector(".cinema-sections")?.scrollIntoView({ behavior: "smooth", block: "start" })}
              >
                <span>{t("cinema.discoverCourses")}</span>
                <Icon name="expand_more" size={26} />
              </button>

              {nowPlaying && (
                <section className="grid-now-playing">
                  <button
                    type="button"
                    className="grid-now-playing-close"
                    onClick={() => {
                      sendCommand("cinema_command", { action: "stop" });
                      setPendingPlaying(null);
                      setOptimisticSeek(null);
                    }}
                    aria-label={t("common.stop")}
                    title={t("common.stop")}
                  >
                    <Icon name="close" size={18} />
                  </button>
                  <span className="grid-now-playing-label">{t("cinema.nowPlaying")}</span>
                  <h2 className="grid-now-playing-title">{nowPlaying.title}</h2>
                  <input
                    type="range"
                    className="grid-now-playing-seek"
                    min={0}
                    max={nowPlaying.duration_seconds || 0}
                    step={1}
                    value={nowPlayingSeekDrag ?? nowPlaying.position_seconds}
                    onChange={(e) => setNowPlayingSeekDrag(Number(e.target.value))}
                    onPointerUp={(e) => {
                      const target = Number((e.target as HTMLInputElement).value);
                      setNowPlayingSeekDrag(null);
                      handleNowPlayingSeekDelta(target - nowPlaying.position_seconds);
                    }}
                    aria-label={t("cinema.seekPosition")}
                  />
                  <div className="grid-now-playing-times">
                    <span>{formatTime(nowPlayingSeekDrag ?? nowPlaying.position_seconds)}</span>
                    <span>{formatTime(nowPlaying.duration_seconds)}</span>
                  </div>
                  <div className="grid-now-playing-controls">
                    <button
                      type="button"
                      className="grid-now-playing-btn"
                      onClick={() => handleNowPlayingSeekDelta(-30)}
                      title={t("cinema.back30")}
                      aria-label={t("cinema.back30")}
                    >
                      <Icon name="replay_30" size={24} />
                    </button>
                    <button
                      type="button"
                      className="grid-now-playing-btn grid-now-playing-btn-main"
                      onClick={handleNowPlayingPlayPause}
                      title={nowPlaying.playing ? t("cinema.pause") : t("cinema.play")}
                      aria-label={nowPlaying.playing ? t("cinema.pause") : t("cinema.play")}
                    >
                      <Icon name={nowPlaying.playing ? "pause" : "play_arrow"} size={30} filled />
                    </button>
                    <button
                      type="button"
                      className="grid-now-playing-btn"
                      onClick={() => handleNowPlayingSeekDelta(30)}
                      title={t("cinema.forward30")}
                      aria-label={t("cinema.forward30")}
                    >
                      <Icon name="forward_30" size={24} />
                    </button>
                  </div>
                </section>
              )}
            </section>
          )}

          <div className="cinema-sections">
            {rows.length === 0 && <p className="cinema-empty">{t("cinema.empty")}</p>}

            {rows.map(([programName, items], rowIndex) => (
              <CinemaRow
                key={programName}
                programName={programName}
                items={items}
                rowIndex={rowIndex}
                onSelect={handleSelect}
                onHover={playHoverSound}
                coursesCountLabel={t("cinema.coursesCount", { count: items.length })}
                accentTitle
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
      )}

      <div
        className={`cinema-layer cinema-video-layer ${isPlayingLayer ? "visible" : ""}`}
        style={!isPlayingLayer ? { display: "none", pointerEvents: "none" } : undefined}
      >
        <div className="cinema-deck-container">
          <video
            ref={deckARef}
            className={`cinema-deck cinema-deck-a ${activeDeck === "A" ? "deck-active" : "deck-idle"}`}
            preload="auto"
            crossOrigin="anonymous"
            onTimeUpdate={(e) => {
              if (activeDeck !== "A" || e.currentTarget.seeking) return;
              const now = Date.now();
              if (now - lastPositionUpdateRef.current < 1000) return;
              lastPositionUpdateRef.current = now;
              setPosition(e.currentTarget.currentTime);
            }}
            onEnded={() => {
              if (activeDeck === "A") handleEnded();
            }}
            onPlay={() => {
              if (activeDeck === "A") {
                setIsPlaying(true);
                reportNowRef.current?.();
              }
            }}
            onPause={() => {
              if (activeDeck === "A") {
                setIsPlaying(false);
                reportNowRef.current?.();
              }
            }}
            onSeeked={(e) => {
              if (activeDeck === "A") {
                setPosition(e.currentTarget.currentTime);
                reportNowRef.current?.();
              }
            }}
            onClick={handlePlayPause}
            playsInline
          >
            {subtitles.map((sub) => (
              <track
                key={sub.id}
                kind="subtitles"
                data-subtitle-id={sub.id}
                src={subtitleSrc(getApiUrl, sub.vtt_url)}
                srcLang={sub.language_code}
                label={sub.language_label}
              />
            ))}
          </video>
          <video
            ref={deckBRef}
            className={`cinema-deck cinema-deck-b ${activeDeck === "B" ? "deck-active" : "deck-idle"}`}
            preload="auto"
            crossOrigin="anonymous"
            onTimeUpdate={(e) => {
              if (activeDeck !== "B" || e.currentTarget.seeking) return;
              const now = Date.now();
              if (now - lastPositionUpdateRef.current < 1000) return;
              lastPositionUpdateRef.current = now;
              setPosition(e.currentTarget.currentTime);
            }}
            onEnded={() => {
              if (activeDeck === "B") handleEnded();
            }}
            onPlay={() => {
              if (activeDeck === "B") {
                setIsPlaying(true);
                reportNowRef.current?.();
              }
            }}
            onPause={() => {
              if (activeDeck === "B") {
                setIsPlaying(false);
                reportNowRef.current?.();
              }
            }}
            onSeeked={(e) => {
              if (activeDeck === "B") {
                setPosition(e.currentTarget.currentTime);
                reportNowRef.current?.();
              }
            }}
            onClick={handlePlayPause}
            playsInline
          >
            {subtitles.map((sub) => (
              <track
                key={sub.id}
                kind="subtitles"
                data-subtitle-id={sub.id}
                src={subtitleSrc(getApiUrl, sub.vtt_url)}
                srcLang={sub.language_code}
                label={sub.language_label}
              />
            ))}
          </video>
        </div>
        {needsTapToPlay && (
          <button className="cinema-tap-to-play" onClick={handlePlayPause}>
            <Icon name="play_arrow" size={56} filled />
            <span>{t("cinema.play")}</span>
          </button>
        )}

        {isPlayingLayer && !isPlaying && !needsTapToPlay && (
          <div className="cinema-pause-overlay" onClick={handlePlayPause}>
            <div className="cinema-pause-center" onClick={(e) => { e.stopPropagation(); }}>
              <div className="pause-media-col">
                <div
                  className="pause-thumb-wrap"
                  onClick={handlePlayPause}
                  title={t("cinema.play")}
                >
                  {selected && thumbnailUrl(selected) ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={thumbnailUrl(selected)!}
                      alt={selected.title}
                      className="pause-thumb-img"
                    />
                  ) : (
                    <div className="pause-thumb-fallback">
                      <AppLogo size={90} className="pause-logo" />
                    </div>
                  )}
                  <div className="pause-thumb-overlay-btn">
                    <Icon name="play_arrow" size={48} filled />
                  </div>
                  <div className="pause-thumb-time">
                    {formatTime(displayPosition)} / {formatTime(duration)}
                  </div>
                </div>

                <div className="pause-logo-mini-wrap">
                  <AppLogo size={80} className="pause-logo" />
                </div>
              </div>

              <div className="pause-details-col">
                <div>
                  <div className="pause-header-row">
                    <span className="cinema-pause-kicker">{t("cinema.pause")}</span>
                    {selected?.program && (
                      <span className="cinema-pause-badge" style={{ color: programAccent }}>
                        {selected.program}
                      </span>
                    )}
                    {selected?.release && (
                      <span className="cinema-pause-year">{selected.release}</span>
                    )}
                    {getResolutionBadge(selected?.width, selected?.height, "HD") && (
                      <span className="cinema-pause-badge-pill">
                        {getResolutionBadge(selected?.width, selected?.height, "HD")}
                      </span>
                    )}
                    {getAudioQualityBadge(selected?.audio_channels, selected?.audio_codec, t("audioBadge.stereo"), t) && (
                      <span className="cinema-pause-badge-pill">
                        {getAudioQualityBadge(selected?.audio_channels, selected?.audio_codec, t("audioBadge.stereo"), t)}
                      </span>
                    )}
                  </div>

                  <h2 className="cinema-pause-title">{selected?.title}</h2>
                </div>

                {selected?.description ? (
                  <div className="pause-description-scroll">
                    <p className="cinema-pause-description-text">{formatCleanDescription(selected.description)}</p>
                  </div>
                ) : (
                  <div style={{ flex: 1 }} />
                )}

                <div className="pause-actions-row">
                  <button
                    className="pause-resume-btn-pill"
                    onClick={handlePlayPause}
                    title={t("cinema.play")}
                  >
                    <Icon name="play_arrow" size={24} filled />
                    <span>{t("cinema.play")}</span>
                  </button>
                  <button
                    className="pause-back-btn-pill"
                    onClick={handleBackToMenu}
                    title={t("cinema.backToMenu")}
                  >
                    <Icon name="arrow_back" size={20} />
                    <span>{t("cinema.backToMenu")}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        <ChapterToast chapters={chapters} videoRef={videoRef} label={t("chapters.toastLabel")} />

        {!hideControls && (
        <div className={`cinema-controls ${isPlayingLayer && (controlsVisible || !isPlaying) ? "visible" : ""}`}>
          <div className="cinema-controls-top">
            <button className="cinema-ctl-btn" onClick={handleBackToMenu} title={t("cinema.backToMenu")}>
              <Icon name="arrow_back" size={26} />
              <span>{t("cinema.backToMenu")}</span>
            </button>
          </div>
          <div className="cinema-controls-bottom">
            <button
              className="cinema-ctl-btn cinema-ctl-round"
              onClick={handlePlayPause}
              title={isPlaying ? t("cinema.pause") : t("cinema.play")}
            >
              <Icon name={isPlaying ? "pause" : "play_arrow"} size={30} filled />
            </button>
            <span className="cinema-time">{formatTime(displayPosition)}</span>
            <div className="chapter-seek">
            <input
              type="range"
              className="cinema-seek"
              min={0}
              max={duration || 0}
              step={1}
              value={Math.min(displayPosition, duration || 0)}
              onChange={(e) => setSeekDragValue(Number(e.target.value))}
              onMouseUp={(e) => {
                const value = Number((e.target as HTMLInputElement).value);
                setSeekDragValue(null);
                setCinemaSync(null);
                if (videoRef.current) seekWhenReady(videoRef.current, value);
                setPosition(value);
              }}
              onTouchEnd={(e) => {
                const value = Number((e.target as HTMLInputElement).value);
                setSeekDragValue(null);
                setCinemaSync(null);
                if (videoRef.current) seekWhenReady(videoRef.current, value);
                setPosition(value);
              }}
              style={{ accentColor: programAccent }}
            />
            <ChapterTicks chapters={chapters} duration={duration} />
            </div>
            <span className="cinema-time">{formatTime(duration)}</span>

            {subtitles.length > 0 && (
              <div className="cinema-subtitle-menu-wrap">
                <button
                  type="button"
                  className={`cinema-ctl-btn cinema-ctl-round ${activeSubtitleId !== "off" ? "active" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowSubtitleMenu((v) => !v);
                  }}
                  title={t("cinema.subtitles")}
                >
                  <Icon name="subtitles" size={24} />
                </button>

                {showSubtitleMenu && (
                  <div className="cinema-subtitle-popover" onClick={(e) => e.stopPropagation()}>
                    <div className="cinema-subtitle-header">
                      {t("cinema.subtitles")}
                    </div>
                    <button
                      type="button"
                      className={`cinema-subtitle-option ${activeSubtitleId === "off" ? "active" : ""}`}
                      onClick={() => {
                        selectSubtitleTrack("off");
                        setShowSubtitleMenu(false);
                      }}
                    >
                      <span>{t("cinema.subtitlesOff")}</span>
                      {activeSubtitleId === "off" && <Icon name="check" size={16} />}
                    </button>
                    {subtitles.map((sub) => (
                      <button
                        key={sub.id}
                        type="button"
                        className={`cinema-subtitle-option ${activeSubtitleId === sub.id ? "active" : ""}`}
                        onClick={() => {
                          selectSubtitleTrack(sub.id);
                          setShowSubtitleMenu(false);
                        }}
                      >
                        <span>{sub.language_label}</span>
                        {activeSubtitleId === sub.id && <Icon name="check" size={16} />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        )}
      </div>

      <div
        className={`cinema-layer cinema-upnext ${isEnded ? "visible" : ""}`}
        style={!isEnded ? { display: "none", pointerEvents: "none" } : undefined}
      >
        <div className="cinema-upnext-layout">
          {endedVideo && wiredDisplayMode === "headless" && (
            <div className="cinema-rating-container">
              <CourseRatingWidget
                videoId={endedVideo.id}
                courseTitle={endedVideo.title}
                channel="cable"
                isCinemaMode={true}
                autoCloseSeconds={waitTimeBetweenCourses > 0 ? waitTimeBetweenCourses : 20}
                onClose={() => setEndedVideo(null)}
              />
            </div>
          )}

          {upNext && (
            <div className="cinema-upnext-card" style={{ "--upnext-accent": upNextAccent } as React.CSSProperties}>
              <span className="cinema-upnext-label">{t("cinema.upNext")}</span>
              <button className="cinema-upnext-thumb" onClick={() => playImmediately(upNext)} title={t("cinema.playNow")}>
                {upNextThumb ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={upNextThumb} alt="" />
                ) : (
                  <Icon name="movie" size={48} color="var(--text-dim)" />
                )}
                <span
                  className="cinema-upnext-ring"
                  style={{ background: `conic-gradient(var(--upnext-accent) ${upNextProgressDeg}deg, color-mix(in srgb, var(--specular) 18%, transparent) 0deg)` }}
                >
                  <span className="cinema-upnext-ring-inner">
                    <Icon name="play_arrow" size={34} filled />
                  </span>
                </span>
              </button>
              <h2 className="cinema-upnext-title">{upNext.title}</h2>
              <p className="cinema-upnext-meta">
                {[upNext.program, upNext.release, formatMinutes(upNext.duration_seconds)].filter(Boolean).join(" · ")}
              </p>
              <p className="cinema-upnext-autoplay">
                {t("cinema.autoPlayIn", { time: formatTime(upNextRemaining) })}
              </p>
              <div className="cinema-upnext-actions">
                <button className="cinema-hero-play" style={{ color: themeFg }} onClick={() => playImmediately(upNext)}>
                  <Icon name="play_arrow" size={22} color={themeFg} filled />
                  {t("cinema.playNow")}
                </button>
                <button className="cinema-ctl-btn" onClick={handleBackToMenu}>
                  <Icon name="arrow_back" size={20} color="currentColor" />
                  {t("cinema.backToMenu")}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <VolumeOsd {...volumeHud} overVideo={phase !== "grid"} />
    </div>
  );
}
