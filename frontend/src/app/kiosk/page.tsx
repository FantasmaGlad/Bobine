"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { usePlaybackSocket, PlaybackEvent } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useAudioClockFollower } from "@/lib/useAudioClockFollower";
import { useVideoClockFollower } from "@/lib/useVideoClockFollower";
import { getDisplayChannel, useDisplayOutputRedirect } from "@/lib/useDisplayOutputRedirect";
import { useKioskRemote } from "@/lib/useKioskRemote";
import Icon from "@/components/Icon";
import { subtitleSrc, useApplySubtitleMode, useVideoSubtitles } from "@/lib/subtitles";
import { chapterJumpTarget, useVideoChapters } from "@/lib/chapters";
import SeekOsd, { useSeekHud } from "@/components/SeekOsd";
import { useMediaSound } from "@/lib/useMediaSound";
import ChapterToast from "@/components/ChapterToast";
import VolumeOsd from "@/components/VolumeOsd";
import { adjustMediaVolume, useVolumeHud, VOLUME_STEP } from "@/lib/volumeHud";
import { getApiUrl } from "@/lib/apiUrl";
import { unloadMedia } from "@/lib/mediaElement";
import CoachStage from "@/components/kiosk/CoachStage";
import PauseOverlay from "@/components/kiosk/PauseOverlay";
import WaitingLayers from "@/components/kiosk/WaitingLayers";
import { applyKioskEvent } from "@/components/kiosk/kioskEvents";
import type { OsdContent } from "@/components/kiosk/media";
import { useKioskClock } from "@/components/kiosk/useKioskClock";
import { useStallWatchdog } from "@/components/kiosk/useStallWatchdog";

export default function KioskPage() {
  const { t } = useAppSettings();
  const [channel] = useState<"cable" | "network">(() => getDisplayChannel("kiosk"));
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const bgVideoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastReportRef = useRef(0);
  const lastAudioReportRef = useRef(0);
  const lastSeekTimeRef = useRef(0);
  const isPrimaryRef = useRef(false);
  const [needsAudioUnlock, setNeedsAudioUnlock] = useState(false);
  const [osd, setOsd] = useState<OsdContent>(null);
  const osdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const video = videoRef;
    const bgVideo = bgVideoRef;
    const audio = audioRef;
    return () => {
      if (osdTimerRef.current) clearTimeout(osdTimerRef.current);
      unloadMedia(video.current);
      unloadMedia(bgVideo.current);
      unloadMedia(audio.current);
    };
  }, []);

  const [volumeHud, showVolumeHud] = useVolumeHud();
  const [seekHud, showSeekHud] = useSeekHud();
  const { now, nextCourse } = useKioskClock(channel);

  const showOsd = useCallback((content: OsdContent) => {
    setOsd(content);
    if (osdTimerRef.current) clearTimeout(osdTimerRef.current);
    osdTimerRef.current = setTimeout(() => setOsd(null), 3000);
  }, []);

  const tryPlay = useCallback((el: HTMLMediaElement | null | undefined) => {
    if (!el) return;
    el.play().catch(() => {
      if (channel === "network") {
        el.muted = true;
        el.play().catch(() => {});
        setNeedsAudioUnlock(true);
      }
    });
  }, [channel]);

  const handleUnlockAudio = useCallback(() => {
    const video = videoRef.current;
    const audio = audioRef.current;
    if (video && video.src) {
      video.muted = false;
      video.play().catch(() => {});
    }
    if (audio && audio.src) {
      audio.muted = false;
      audio.play().catch(() => {});
    }
    setNeedsAudioUnlock(false);
  }, []);

  const handleEvent = useCallback(
    (evt: PlaybackEvent) => applyKioskEvent(
      evt,
      { video: videoRef.current, bgVideo: bgVideoRef.current, audio: audioRef.current },
      { isPrimary: () => isPrimaryRef.current, lastSeekTime: () => lastSeekTimeRef.current, tryPlay, showOsd, showVolumeHud },
    ),
    [showOsd, showVolumeHud, tryPlay]
  );

  const { state, sendCommand, serverNow, isPrimary, displayOutputCable, displayOutputNetwork } = usePlaybackSocket(handleEvent, "kiosk", channel, undefined, "kiosk");

  const subtitles = useVideoSubtitles(state.current_video?.id, getApiUrl);
  useApplySubtitleMode([videoRef], subtitles, state.subtitle ?? null);
  const chapters = useVideoChapters(state.current_video?.id, getApiUrl);
  useVideoClockFollower({
    videoRef,
    state,
    serverNow,
    tryPlay,
    onSeek: () => {
      lastSeekTimeRef.current = Date.now();
    },
  });
  useAudioClockFollower({ audioRef, state, serverNow, tryPlay });
  useEffect(() => {
    isPrimaryRef.current = isPrimary;
  }, [isPrimary]);
  useDisplayOutputRedirect("kiosk", displayOutputCable, displayOutputNetwork);

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video || !isPrimary) return;
    const now = Date.now();
    if (now - lastReportRef.current > 1000) {
      lastReportRef.current = now;
      sendCommand("report_position", { position_seconds: video.currentTime });
    }
  };

  const handleAudioTimeUpdate = () => {
    const audio = audioRef.current;
    if (!audio || !isPrimary) return;
    const now = Date.now();
    if (now - lastAudioReportRef.current > 1000) {
      lastAudioReportRef.current = now;
      sendCommand("audio_report_position", { position_seconds: audio.currentTime });
    }
  };

  useStallWatchdog(videoRef, lastSeekTimeRef);

  useMediaSound(videoRef, state.sound);
  useMediaSound(audioRef, state.sound);

  const seekVideoTo = (seconds: number) => {
    sendCommand("seek", { position_seconds: seconds });
    showSeekHud({ position: seconds, duration: videoRef.current?.duration || state.current_video?.duration_seconds || 0 });
  };

  const jumpChapter = (direction: "next" | "prev") => {
    if (!state.current_video) return;
    const cur = videoRef.current?.currentTime || state.position_seconds || 0;
    const target = chapterJumpTarget(chapters, cur, direction);
    if (target !== null) seekVideoTo(target);
  };

  useKioskRemote(() => {
    return {
      onPlayPause: () => {
        if (state.current_video) {
          sendCommand(state.state === "playing" ? "pause" : "play");
        } else if (state.current_audio_course) {
          sendCommand(state.audio_playing ? "pause" : "play");
        }
      },
      onEnter: () => {
        if (state.current_video) {
          sendCommand(state.state === "playing" ? "pause" : "play");
        } else if (state.current_audio_course) {
          sendCommand(state.audio_playing ? "pause" : "play");
        }
      },
      onLeft: () => {
        if (state.current_video) {
          const cur = videoRef.current?.currentTime || state.position_seconds || 0;
          seekVideoTo(Math.max(0, cur - 10));
        } else if (state.current_audio_course) {
          const cur = audioRef.current?.currentTime || state.audio_position_seconds || 0;
          sendCommand("seek", { position_seconds: Math.max(0, cur - 10) });
        }
      },
      onRight: () => {
        if (state.current_video) {
          const cur = videoRef.current?.currentTime || state.position_seconds || 0;
          const dur = videoRef.current?.duration || state.current_video.duration_seconds || 0;
          seekVideoTo(Math.min(dur, cur + 10));
        } else if (state.current_audio_course) {
          const cur = audioRef.current?.currentTime || state.audio_position_seconds || 0;
          const dur = audioRef.current?.duration || 0;
          sendCommand("seek", { position_seconds: Math.min(dur, cur + 10) });
        }
      },
      onChapterNext: () => jumpChapter("next"),
      onChapterPrev: () => jumpChapter("prev"),
      onVolumeUp: () => showVolumeHud(adjustMediaVolume([videoRef.current, audioRef.current], VOLUME_STEP)),
      onVolumeDown: () => showVolumeHud(adjustMediaVolume([videoRef.current, audioRef.current], -VOLUME_STEP)),
      onBack: () => {
        if (state.current_video || state.current_audio_course) {
          sendCommand("stop");
        }
      },
      onMute: () => showVolumeHud(adjustMediaVolume([videoRef.current, audioRef.current], 0, true)),
    };
  });

  const programAccent = "var(--accent-primary)";
  const isVideoLayer = state.state === "playing" || state.state === "paused";
  const isPaused = state.state === "paused";
  const isCoachMode = state.state === "coach_mode";
  const coachBackgroundId = state.current_background?.id ?? state.current_audio_course?.background_id ?? null;
  const backgroundIsImage = state.current_background?.is_image ?? false;
  const backgroundLayerActive = state.state === "background" || (isCoachMode && coachBackgroundId !== null);

  return (
    <div className="kiosk-root">
      <WaitingLayers t={t} state={state} now={now} nextCourse={nextCourse} />

      <div
        className={`kiosk-layer kiosk-video-layer ${isVideoLayer ? "visible" : ""}`}
        onClick={() => {
          if (isVideoLayer && state.current_video) {
            sendCommand(state.state === "playing" ? "pause" : "play");
          }
        }}
      >
        <video
          ref={videoRef}
          className="kiosk-video"
          crossOrigin="anonymous"
          onTimeUpdate={handleTimeUpdate}
          onEnded={() => sendCommand("video_ended", { video_id: state.current_video?.id })}
          onClick={(e) => {
            e.stopPropagation();
            if (state.current_video) {
              sendCommand(state.state === "playing" ? "pause" : "play");
            }
          }}
          preload="auto"
          playsInline
        >
          {subtitles.map((sub, i) => (
            <track
              key={sub.id}
              kind="subtitles"
              data-subtitle-id={sub.id}
              src={subtitleSrc(getApiUrl, sub.vtt_url)}
              srcLang={sub.language_code}
              label={sub.language_label}
              default={i === 0}
            />
          ))}
        </video>
      </div>

      {state.current_video && <SeekOsd {...seekHud} visible={seekHud.visible} chapters={chapters} />}

      <ChapterToast chapters={chapters} videoRef={videoRef} label={t("chapters.toastLabel")} />

      <div className={`kiosk-layer kiosk-video-layer ${backgroundLayerActive && !backgroundIsImage ? "visible" : ""}`}>
        <video ref={bgVideoRef} className="kiosk-video" loop muted playsInline autoPlay />
      </div>

      <div className={`kiosk-layer kiosk-video-layer ${backgroundLayerActive && backgroundIsImage ? "visible" : ""}`}>
        {backgroundIsImage && coachBackgroundId !== null && (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="kiosk-video" src={getApiUrl(`/backgrounds/${coachBackgroundId}/stream`)} alt="" />
        )}
      </div>

      <div
        className={`kiosk-layer kiosk-coach-mode ${isCoachMode ? "visible" : ""} ${
          coachBackgroundId !== null ? "with-background" : ""
        }`}
      >
        <audio
          ref={audioRef}
          onTimeUpdate={handleAudioTimeUpdate}
          onEnded={() => sendCommand("audio_track_ended", { track_index: state.audio_track_index })}
        />
        <CoachStage t={t} state={state} programAccent={programAccent} />
      </div>

      {isPaused && <PauseOverlay t={t} state={state} programAccent={programAccent} onResume={() => sendCommand("play")} />}

      {osd && (
        <div className="kiosk-osd">
          <Icon name={osd.icon} size={28} filled />
          <span className="kiosk-osd-label">{osd.label}</span>
        </div>
      )}

      {needsAudioUnlock && (
        <button className="kiosk-unlock-audio" onClick={handleUnlockAudio}>
          <Icon name="volume_off" size={22} />
          {t("kiosk.unlockAudioLabel")}
        </button>
      )}

      <VolumeOsd {...volumeHud} overVideo={Boolean(state.current_video)} />
    </div>
  );
}
