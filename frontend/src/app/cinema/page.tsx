"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import ChapterToast from "@/components/ChapterToast";
import CinemaControls from "@/components/cinema/CinemaControls";
import CinemaDeck from "@/components/cinema/CinemaDeck";
import CinemaGrid from "@/components/cinema/CinemaGrid";
import { EmptyScreen, StandbyScreen } from "@/components/cinema/CinemaScreens";
import { seekWhenReady } from "@/components/cinema/media";
import PauseScreen from "@/components/PauseScreen";
import { useSeekHud } from "@/components/SeekOsd";
import { cinemaRemoteKeys } from "@/components/cinema/remoteKeys";
import UpNextLayer, { UP_NEXT_AUTOPLAY_SECONDS } from "@/components/cinema/UpNextLayer";
import { useCinemaVideos } from "@/components/cinema/useCinemaVideos";
import { useNowPlaying } from "@/components/cinema/useNowPlaying";
import { useCinemaReport, useStallWatchdog } from "@/components/cinema/usePlaybackGuards";
import Icon from "@/components/Icon";
import VolumeOsd from "@/components/VolumeOsd";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { getApiUrl } from "@/lib/apiUrl";
import { chapterJumpTarget, useVideoChapters } from "@/lib/chapters";
import { thumbnailUrl, type CinemaVideo } from "@/lib/cinemaCatalog";
import { videoStreamUrl } from "@/lib/clientCodecSupport";
import { buildOutputUrl } from "@/lib/displayChannel";
import { unloadMedia } from "@/lib/mediaElement";
import type { ClockAnchor } from "@/lib/playbackClock";
import { useApplySubtitleMode, useVideoSubtitles } from "@/lib/subtitles";
import { getDisplayChannel, isWiredDisplay, useDisplayOutputRedirect } from "@/lib/useDisplayOutputRedirect";
import { useKioskRemote } from "@/lib/input/useKioskRemote";
import { useMediaClockFollower, type ClockTarget } from "@/lib/useMediaClockFollower";
import { useMediaSound } from "@/lib/useMediaSound";
import { useScrubber } from "@/lib/useScrubber";
import { useStoryboard } from "@/lib/useStoryboard";
import { usePlaybackSocket, type CinemaCommandExtra } from "@/lib/usePlaybackSocket";
import { adjustMediaVolume, useVolumeHud } from "@/lib/volumeHud";
import type { OutputId } from "@/lib/outputs";

const CONTROLS_HIDE_MS = 3000;

type Phase = "grid" | "playing" | "ended";
type Deck = "A" | "B";
type CinemaCommand = (action: string, positionSeconds: number, videoId?: number, extra?: CinemaCommandExtra) => void;

interface CinemaSync {
  anchor: ClockAnchor;
  videoId: number;
}

function selectCinemaTarget(sync: CinemaSync | null): ClockTarget {
  if (!sync) return { anchor: null, mode: null };
  return { anchor: sync.anchor, mode: sync.anchor.running ? "playing" : "paused", key: sync.videoId };
}

function prepare(el: HTMLVideoElement, video: CinemaVideo) {
  el.src = videoStreamUrl(getApiUrl, video.id);
  el.currentTime = 0;
  el.volume = 1.0;
  el.muted = false;
  el.load();
}

export default function CinemaPage() {
  const { t, wiredDisplayMode } = useAppSettings();
  const deckA = useRef<HTMLVideoElement | null>(null);
  const deckB = useRef<HTMLVideoElement | null>(null);
  const [activeDeck, setActiveDeck] = useState<Deck>("A");
  const activeDeckRef = useRef<Deck>("A");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [volumeHud, showVolumeHud] = useVolumeHud();
  const [endedVideo, setEndedVideo] = useState<CinemaVideo | null>(null);
  const [phase, setPhase] = useState<Phase>("grid");
  const [selected, setSelected] = useState<CinemaVideo | null>(null);
  const [activeSubtitle, setActiveSubtitle] = useState<number | "off">("off");
  const [standby, setStandby] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [needsTap, setNeedsTap] = useState(false);
  const [position, setPosition] = useState(0);
  const [seekDrag, setSeekDrag] = useState<number | null>(null);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [upNext, setUpNext] = useState<CinemaVideo | null>(null);
  const [upNextRemaining, setUpNextRemaining] = useState(UP_NEXT_AUTOPLAY_SECONDS);
  const [cinemaSync, setCinemaSync] = useState<CinemaSync | null>(null);
  const [channel] = useState<OutputId>(() => getDisplayChannel("cinema"));
  const lastPositionUpdate = useRef(0);
  const lastSeek = useRef(0);
  const controlsTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const deckUnloadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const upNextTask = useRef<ReturnType<typeof setInterval> | null>(null);
  const cinemaCmd = useRef<CinemaCommand | null>(null);

  const subtitles = useVideoSubtitles(selected?.id, getApiUrl);
  useApplySubtitleMode([deckA, deckB], subtitles, activeSubtitle);
  const chapters = useVideoChapters(selected?.id, getApiUrl);
  const storyboard = useStoryboard(selected?.id);
  const hideControls = wiredDisplayMode === "dual_screen" && isWiredDisplay();
  const { state, displayOutputs, sendCommand, cinemaState, libraryVersion, serverNow } = usePlaybackSocket(
    undefined, undefined, channel, (action, positionSeconds, videoId, extra) => cinemaCmd.current?.(action, positionSeconds, videoId, extra), "cinema",
  );
  const videos = useCinemaVideos(libraryVersion);
  const remote = useNowPlaying(cinemaState, sendCommand);
  useMediaSound(deckA, state.sound);
  useMediaSound(deckB, state.sound);
  useDisplayOutputRedirect("cinema", displayOutputs);

  useEffect(() => {
    activeDeckRef.current = activeDeck;
    videoRef.current = activeDeck === "A" ? deckA.current : deckB.current;
  }, [activeDeck]);

  const [subtitleFor, setSubtitleFor] = useState(selected?.id);
  if (subtitleFor !== selected?.id) {
    setSubtitleFor(selected?.id);
    setActiveSubtitle("off");
  }

  useEffect(() => {
    if (state.state === "coach_mode") window.location.replace(buildOutputUrl("kiosk", window.location.search, channel));
  }, [state.state, channel]);

  const fresh = selected && !(selected.thumbnail_path && selected.description)
    ? videos.find((v) => Number(v.id) === Number(selected.id))
    : undefined;
  if (selected && fresh && Object.entries(fresh).some(([key, value]) => selected[key as keyof typeof selected] !== value)) {
    setSelected({ ...selected, ...fresh });
  }

  const wakeControls = useCallback(() => {
    setControlsVisible(true);
    if (controlsTimer.current) clearTimeout(controlsTimer.current);
    controlsTimer.current = setTimeout(() => setControlsVisible(false), CONTROLS_HIDE_MS);
  }, []);

  const clearUpNextTask = () => {
    if (upNextTask.current) clearInterval(upNextTask.current);
    upNextTask.current = null;
  };

  const failPlay = () => {
    setIsPlaying(false);
    setNeedsTap(true);
  };

  const swapDecks = useCallback((idle: HTMLVideoElement, current: HTMLVideoElement, video: CinemaVideo) => {
    if (deckUnloadTimer.current) clearTimeout(deckUnloadTimer.current);
    deckUnloadTimer.current = null;
    prepare(idle, video);
    idle.addEventListener("canplay", () => {
      idle.play().then(() => {
        setIsPlaying(true);
        const next = activeDeckRef.current === "A" ? "B" : "A";
        activeDeckRef.current = next;
        setActiveDeck(next);
        videoRef.current = idle;
        deckUnloadTimer.current = setTimeout(() => {
          deckUnloadTimer.current = null;
          unloadMedia(current);
        }, 450);
      }).catch(failPlay);
    }, { once: true });
  }, []);

  const startPlayback = useCallback((video: CinemaVideo) => {
    const current = activeDeckRef.current === "A" ? deckA.current : deckB.current;
    const idle = activeDeckRef.current === "A" ? deckB.current : deckA.current;
    setNeedsTap(false);
    wakeControls();
    if (isPlaying && idle && current) return swapDecks(idle, current, video);
    const target = current || idle;
    if (!target) return;
    prepare(target, video);
    target.play().then(() => setIsPlaying(true)).catch(failPlay);
  }, [isPlaying, wakeControls, swapDecks]);

  const handleSelect = useCallback((video: CinemaVideo) => {
    setCinemaSync(null);
    clearUpNextTask();
    setUpNext(null);
    setEndedVideo(null);
    setSelected(video);
    setPhase("playing");
    setPosition(0);
    startPlayback(video);
  }, [startPlayback]);

  const backToMenu = useCallback(() => {
    setCinemaSync(null);
    clearUpNextTask();
    unloadMedia(deckA.current);
    unloadMedia(deckB.current);
    setPhase("grid");
    setSelected(null);
    setUpNext(null);
    setEndedVideo(null);
    setIsPlaying(false);
    setNeedsTap(false);
    setPosition(0);
  }, []);

  const handleEnded = useCallback(() => {
    setCinemaSync(null);
    videoRef.current?.pause();
    setIsPlaying(false);
    if (selected) setEndedVideo(selected);
    const candidates = videos.filter((v) => v.id !== selected?.id);
    if (candidates.length === 0) return backToMenu();
    const next = candidates[Math.floor(Math.random() * candidates.length)];
    setUpNext(next);
    setUpNextRemaining(UP_NEXT_AUTOPLAY_SECONDS);
    setPhase("ended");
    clearUpNextTask();
    upNextTask.current = setInterval(() => {
      setUpNextRemaining((prev) => {
        if (prev > 1) return prev - 1;
        clearUpNextTask();
        handleSelect(next);
        return 0;
      });
    }, 1000);
  }, [videos, selected, backToMenu, handleSelect]);

  useEffect(() => {
    const a = deckA;
    const b = deckB;
    return () => {
      clearUpNextTask();
      if (deckUnloadTimer.current) clearTimeout(deckUnloadTimer.current);
      if (controlsTimer.current) clearTimeout(controlsTimer.current);
      unloadMedia(a.current);
      unloadMedia(b.current);
    };
  }, []);

  const playPause = () => {
    const el = videoRef.current;
    if (!el) return;
    setCinemaSync(null);
    if (needsTap) {
      el.play().then(() => { setIsPlaying(true); setNeedsTap(false); }).catch(() => {});
    } else if (el.paused) {
      el.play().then(() => setIsPlaying(true)).catch(() => {});
    } else {
      el.pause();
      setIsPlaying(false);
    }
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

  const scrubber = useScrubber();
  const [scrubHud, showScrubHud] = useSeekHud();
  const scrub = (direction: 1 | -1) => {
    const el = videoRef.current;
    if (!el) return;
    scrubber.press(direction, el.currentTime || 0, el.duration || 0, {
      onPreview: (seconds) => {
        setPosition(seconds);
        showScrubHud({ position: seconds, duration: el.duration || 0 });
        wakeControls();
      },
      onCommit: (seconds) => {
        setCinemaSync(null);
        if (videoRef.current) videoRef.current.currentTime = seconds;
      },
      onChapter: (dir, from) => {
        const target = chapterJumpTarget(chapters, from, dir === 1 ? "next" : "prev");
        if (target === null) return false;
        seekBy(target - (videoRef.current?.currentTime || 0));
        showScrubHud({ position: target, duration: el.duration || 0 });
        return true;
      },
    });
  };

  const seekTo = (value: number) => {
    setSeekDrag(null);
    setCinemaSync(null);
    if (videoRef.current) seekWhenReady(videoRef.current, value);
    setPosition(value);
  };

  const changeVolume = useCallback((delta: number, toggleMute = false) => {
    showVolumeHud(adjustMediaVolume([deckA.current, deckB.current], delta, toggleMute));
    wakeControls();
  }, [showVolumeHud, wakeControls]);

  useKioskRemote(() => cinemaRemoteKeys({
    phase, standby, setStandby, volume: changeVolume, playPause, back: backToMenu, seekBy, scrub,
    chapter: (direction) => {
      const el = videoRef.current;
      const target = el ? chapterJumpTarget(chapters, el.currentTime || 0, direction) : null;
      if (el && target !== null) seekBy(target - (el.currentTime || 0));
    },
    playNext: () => { if (upNext) handleSelect(upNext); },
  }));

  useEffect(() => {
    cinemaCmd.current = (action, positionSeconds, videoId, extra) => {
      if (action === "stop") return backToMenu();
      if (action === "launch") {
        const known = videos.find((v) => Number(v.id) === Number(videoId));
        const video = known ?? (videoId ? { id: Number(videoId), title: extra?.title || "", program: null, release: null, duration_seconds: extra?.duration_seconds ?? null, thumbnail_path: null } : undefined);
        if (!video) return;
        handleSelect(video);
        if (extra?.clock && extra.clock_video_id === Number(video.id)) setCinemaSync({ anchor: extra.clock, videoId: extra.clock_video_id });
        return;
      }
      const el = videoRef.current;
      if (!el || phase !== "playing") return;
      if (action === "pause") {
        el.pause();
        setIsPlaying(false);
      } else if (action === "play") {
        el.play().then(() => setIsPlaying(true)).catch(() => {});
      } else if (action === "seek") {
        lastSeek.current = Date.now();
        seekWhenReady(el, positionSeconds, () => setPosition(positionSeconds));
      }
      if (extra?.clock && extra.clock_video_id !== undefined && Number(selected?.id) === extra.clock_video_id) {
        setCinemaSync({ anchor: extra.clock, videoId: extra.clock_video_id });
      }
    };
  }, [phase, backToMenu, videos, handleSelect, selected?.id]);

  const cinemaMediaRef = useMemo(() => ({ get current() { return videoRef.current; } }), []);
  useMediaClockFollower({
    mediaRef: cinemaMediaRef,
    state: cinemaSync,
    select: selectCinemaTarget,
    isMediaForKey: (el, key) => el.src.includes(`/videos/${key}/stream`),
    serverNow,
    tryPlay: (el) => { el?.play().catch(() => {}); },
    onSeek: () => { lastSeek.current = Date.now(); },
  });
  useStallWatchdog(videoRef, lastSeek);
  const reportNow = useCinemaReport(phase === "playing", selected, videoRef, sendCommand);

  const playingLayer = phase === "playing";
  const duration = selected?.duration_seconds ?? 0;
  const shownPosition = seekDrag ?? position;

  const reportPosition = useCallback((seconds: number) => {
    if (Date.now() - lastPositionUpdate.current < 1000) return;
    lastPositionUpdate.current = Date.now();
    setPosition(seconds);
  }, []);

  const deckProps = (deck: Deck) => ({
    active: activeDeck === deck,
    subtitles,
    onClick: playPause,
    onEnded: handleEnded,
    onPosition: reportPosition,
    onPlaying: (playing: boolean) => {
      setIsPlaying(playing);
      reportNow.current?.();
    },
    onSeeked: (seconds: number) => {
      setPosition(seconds);
      reportNow.current?.();
    },
  });

  return (
    <div className="cinema-root" onMouseMove={playingLayer ? wakeControls : undefined} onTouchStart={playingLayer ? wakeControls : undefined} onPointerDown={playingLayer ? wakeControls : undefined}>
      {videos.length === 0 && <EmptyScreen />}
      {(hideControls || standby) && phase === "grid" && <StandbyScreen />}
      {!(hideControls || standby) && <CinemaGrid visible={phase === "grid"} videos={videos} remote={remote} onSelect={handleSelect} />}
      <div className={`cinema-layer cinema-video-layer ${playingLayer ? "visible" : ""}`} style={!playingLayer ? { display: "none", pointerEvents: "none" } : undefined}>
        <div className="cinema-deck-container">
          <CinemaDeck deck="a" ref={deckA} {...deckProps("A")} />
          <CinemaDeck deck="b" ref={deckB} {...deckProps("B")} />
        </div>
        {needsTap && (
          <button className="cinema-tap-to-play" onClick={playPause}>
            <Icon name="play_arrow" size={56} filled />
            <span>{t("cinema.play")}</span>
          </button>
        )}
        {playingLayer && !isPlaying && !needsTap && (
          <PauseScreen t={t} media={selected} thumbnail={selected ? thumbnailUrl(selected) : null} position={shownPosition} duration={duration}
            kicker={t("cinema.pause")} resumeLabel={t("cinema.play")} onResume={playPause} back={{ label: t("cinema.backToMenu"), onBack: backToMenu }} />
        )}
        {isPlaying && <ChapterToast chapters={chapters} videoRef={videoRef} label={t("chapters.toastLabel")} lifted={!hideControls && playingLayer && controlsVisible} />}
        {!hideControls && (
          <CinemaControls visible={playingLayer && (controlsVisible || !isPlaying)} playing={isPlaying} position={shownPosition} duration={duration} chapters={chapters}
            board={storyboard} scrubbing={seekDrag !== null || scrubHud.visible}
            subtitles={subtitles} activeSubtitle={activeSubtitle} onSubtitle={setActiveSubtitle} onPlayPause={playPause} onBack={backToMenu} onDrag={setSeekDrag} onSeek={seekTo} />
        )}
      </div>
      <UpNextLayer visible={phase === "ended"} ended={endedVideo} upNext={upNext} remaining={upNextRemaining} onPlay={handleSelect} onBack={backToMenu} onCloseRating={() => setEndedVideo(null)} />
      <VolumeOsd {...volumeHud} overVideo={phase !== "grid"} />
    </div>
  );
}
