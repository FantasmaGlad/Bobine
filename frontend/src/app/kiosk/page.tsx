"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { usePlaybackSocket, PlaybackEvent } from "@/lib/usePlaybackSocket";
import { videoStreamUrl } from "@/lib/clientCodecSupport";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useAudioClockFollower } from "@/lib/useAudioClockFollower";
import { useVideoClockFollower } from "@/lib/useVideoClockFollower";
import { getDisplayChannel, useDisplayOutputRedirect } from "@/lib/useDisplayOutputRedirect";
import { useKioskRemote } from "@/lib/useKioskRemote";
import Icon from "@/components/Icon";
import AppLogo from "@/components/AppLogo";
import { getResolutionBadge, getAudioQualityBadge } from "@/lib/videoBadges";
import { formatCleanDescription } from "@/lib/formatDescription";
import { subtitleSrc, useApplySubtitleMode, useVideoSubtitles } from "@/lib/subtitles";
import { chapterJumpTarget, useVideoChapters } from "@/lib/chapters";
import SeekOsd, { useSeekHud } from "@/components/SeekOsd";
import { useMediaSound } from "@/lib/useMediaSound";
import ChapterToast from "@/components/ChapterToast";
import VolumeOsd from "@/components/VolumeOsd";
import { adjustMediaVolume, useVolumeHud, VOLUME_STEP } from "@/lib/volumeHud";
import { getApiUrl } from "@/lib/apiUrl";
import { formatTime, formatWallClock } from "@/lib/format";
import { unloadMedia } from "@/lib/mediaElement";

function formatDuration(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function getThumbnailSrc(thumb?: string | null): string | null {
  if (!thumb) return null;
  const filename = thumb.split("/").pop();
  return filename ? getApiUrl(`/thumbnails/${filename}`) : null;
}

type OsdContent = { icon: string; label: string } | null;

interface NextCourse {
  run_at: string;
  title: string | null;
}

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
  const [now, setNow] = useState(new Date());
  const clockOffsetRef = useRef<number>(0);
  const [nextCourse, setNextCourse] = useState<NextCourse | null>(null);
  const [, setFastTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setFastTick((t) => (t + 1) % 1_000_000), 200);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const syncClock = () => {
      fetch(getApiUrl("/time"), { cache: "no-store" })
        .then((res) => res.ok ? res.json() : null)
        .then((data) => {
          if (data && typeof data.server_ts === "number") {
            clockOffsetRef.current = data.server_ts - Date.now();
          }
        })
        .catch((err) => {
          console.warn("[clock] Synchronisation heure serveur échouée :", err);
        });
    };
    syncClock();
    const syncId = setInterval(syncClock, 60 * 1000);
    const tickId = setInterval(() => setNow(new Date(Date.now() + clockOffsetRef.current)), 1000);
    return () => {
      clearInterval(syncId);
      clearInterval(tickId);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const fetchNext = () => {
      fetch(getApiUrl(`/schedule/next?channel=${channel}`), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!cancelled) setNextCourse(data);
        })
        .catch(() => {
          if (!cancelled) setNextCourse(null);
        });
    };
    fetchNext();
    const id = setInterval(fetchNext, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [channel]);

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
    (evt: PlaybackEvent) => {
      const { cause, data } = evt;
      const video = videoRef.current;
      const bgVideo = bgVideoRef.current;
      const audio = audioRef.current;

      const currentTrack =
        data.audio_tracks && data.audio_track_index !== null && data.audio_track_index !== undefined
          ? data.audio_tracks[data.audio_track_index]
          : null;
      const backgroundId = data.current_background?.id ?? data.current_audio_course?.background_id ?? null;
      const backgroundIsImage = data.current_background?.is_image ?? false;

      const applyVolume = (el: HTMLMediaElement) => {
        el.muted = false;
        el.volume = data.volume / 100;
      };

      const syncAudioToTrack = (resetTime: boolean) => {
        if (!audio || !currentTrack) return;
        const src = getApiUrl(`/audio/tracks/${currentTrack.id}/stream`);
        if (!audio.src || !audio.src.endsWith(src)) {
          audio.src = src;
          audio.load();
        }
        void resetTime;
        applyVolume(audio);
        if (!data.audio_playing) audio.pause();
      };

      const syncBackgroundLayer = () => {
        if (!bgVideo) return;
        if (!backgroundId || backgroundIsImage) {
          unloadMedia(bgVideo);
          return;
        }
        const bgSrc = getApiUrl(`/backgrounds/${backgroundId}/stream`);
        if (!bgVideo.src || !bgVideo.src.endsWith(bgSrc)) {
          bgVideo.src = bgSrc;
          bgVideo.load();
          if (data.audio_playing) bgVideo.play().catch(() => {});
        }
      };

      switch (cause) {
        case "sync": {
          if (!data.current_video) unloadMedia(video);
          if (!backgroundId || backgroundIsImage) unloadMedia(bgVideo);
          if (!data.current_audio_course) unloadMedia(audio);
          if (backgroundId && !backgroundIsImage && bgVideo) {
            const bgSrc = getApiUrl(`/backgrounds/${backgroundId}/stream`);
            if (!bgVideo.src || !bgVideo.src.endsWith(bgSrc)) bgVideo.src = bgSrc;
            if (!data.current_audio_course || data.audio_playing) bgVideo.play().catch(() => {});
            else bgVideo.pause();
          }
          if (data.current_audio_course && audio && currentTrack) {
            const aSrc = getApiUrl(`/audio/tracks/${currentTrack.id}/stream`);
            if (!audio.src || !audio.src.endsWith(aSrc)) {
              audio.src = aSrc;
              audio.load();
            }
            applyVolume(audio);
          }
          if (!video || !data.current_video) break;
          const src = videoStreamUrl(getApiUrl, data.current_video.id);
          applyVolume(video);
          const srcChanged = !video.src || !video.src.endsWith(src);
          if (srcChanged) {
            video.src = src;
            video.load();
          }
          break;
        }
        case "position_tick": {
          if (isPrimaryRef.current) break;
          if (Date.now() - lastSeekTimeRef.current < 3000) break;
          if (data.current_audio_course && audio && currentTrack) {
            if (bgVideo && bgVideo.src) {
              if (data.audio_playing && bgVideo.paused) tryPlay(bgVideo);
              else if (!data.audio_playing && !bgVideo.paused) bgVideo.pause();
            }
          }
          break;
        }
        case "load": {
          unloadMedia(bgVideo);
          unloadMedia(audio);
          if (!video || !data.current_video) break;
          video.src = videoStreamUrl(getApiUrl, data.current_video.id);
          applyVolume(video);
          video.load();
          break;
        }
        case "load_background": {
          unloadMedia(video);
          unloadMedia(audio);
          if (backgroundIsImage) {
            unloadMedia(bgVideo);
            break;
          }
          if (!bgVideo || !data.current_background) break;
          bgVideo.src = getApiUrl(`/backgrounds/${data.current_background.id}/stream`);
          bgVideo.load();
          bgVideo.play().catch(() => {});
          break;
        }
        case "load_audio_course":
        case "audio_set_background": {
          unloadMedia(video);
          syncBackgroundLayer();
          if (cause === "load_audio_course") syncAudioToTrack(true);
          break;
        }
        case "audio_next_track":
        case "audio_previous_track":
        case "audio_jump_to_track":
        case "audio_restart_track":
          syncBackgroundLayer();
          syncAudioToTrack(true);
          break;
        case "play":
          if (data.current_audio_course) {
            tryPlay(audio);
            if (bgVideo && bgVideo.src) tryPlay(bgVideo);
          }
          break;
        case "pause":
          if (data.current_audio_course) {
            audio?.pause();
            bgVideo?.pause();
          } else {
            video?.pause();
          }
          break;
        case "stop":
          unloadMedia(video);
          unloadMedia(bgVideo);
          unloadMedia(audio);
          break;
        case "seek":
          showOsd({
            icon: "fast_forward",
            label: `${formatTime(data.position_seconds)} / ${formatTime(data.current_video?.duration_seconds)}`,
          });
          break;
        case "volume":
          if (video) applyVolume(video);
          if (audio) applyVolume(audio);
          showVolumeHud({ level: data.volume / 100, muted: false });
          break;
        case "speed":
          showOsd({ icon: "speed", label: `${data.speed.toFixed(2)}x` });
          break;
        default:
          break;
      }
    },
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

  const program = state.current_video?.program ?? state.current_audio_course?.program ?? undefined;
  const programAccent = "var(--accent-primary)";
  const isIdle = state.state === "waiting" || state.state === "offline";
  const isVideoLayer = state.state === "playing" || state.state === "paused";
  const isPaused = state.state === "paused";
  const isCoachMode = state.state === "coach_mode";
  const coachBackgroundId = state.current_background?.id ?? state.current_audio_course?.background_id ?? null;
  const backgroundIsImage = state.current_background?.is_image ?? false;
  const backgroundLayerActive = state.state === "background" || (isCoachMode && coachBackgroundId !== null);
  const currentTrack =
    state.audio_tracks && state.audio_track_index !== null && state.audio_track_index !== undefined
      ? state.audio_tracks[state.audio_track_index]
      : null;
  const audioTrackRemaining = currentTrack?.duration_seconds
    ? Math.max(0, currentTrack.duration_seconds - state.audio_position_seconds)
    : null;
  const audioTrackProgress = currentTrack?.duration_seconds
    ? Math.min(100, (state.audio_position_seconds / currentTrack.duration_seconds) * 100)
    : 0;

  const nextCourseRemaining = nextCourse
    ? Math.max(0, (new Date(nextCourse.run_at).getTime() - now.getTime()) / 1000)
    : null;

  const duration = state.current_video?.duration_seconds ?? 0;
  const pauseProgressPercent = duration > 0 ? Math.min(100, (state.position_seconds / duration) * 100) : 0;

  const nextPlaylistItem = state.playlist_items && state.playlist_index !== null && state.playlist_index !== undefined
    ? state.playlist_items[state.playlist_index + 1]
    : null;

  return (
    <div className="kiosk-root">
      <div className={`kiosk-layer kiosk-waiting ${isIdle ? "visible" : ""}`}>
        <div className="kiosk-waiting-content">
          <span className="kiosk-waiting-clock" suppressHydrationWarning>{formatWallClock(now)}</span>
          <div className="kiosk-waiting-logo-wrap">
            <AppLogo className="kiosk-waiting-stage-logo" />
          </div>
          <div className="kiosk-waiting-next">
            {nextCourse ? (
              <>
                <span className="kiosk-waiting-next-label">
                  {t("kiosk.nextCourseLabel")}
                </span>
                <span className="kiosk-waiting-next-title">
                  {nextCourse.title ?? t("kiosk.scheduledCourseFallback")}
                </span>
                <span className="kiosk-waiting-next-countdown">
                  {formatDuration(nextCourseRemaining ?? 0)}
                </span>
              </>
            ) : (
              <span className="kiosk-waiting-next-empty">
                {t("kiosk.waitingForNextCourse")}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className={`kiosk-layer kiosk-playlist-waiting ${state.state === "playlist_waiting" ? "visible" : ""}`}>
        <AppLogo size={110} className="kiosk-waiting-logo" />
        <span className="kiosk-clock" suppressHydrationWarning>{formatWallClock(now)}</span>
        <div className="kiosk-playlist-info">
          <span className="kiosk-playlist-label">{t("kiosk.activePlaylist")}</span>
          <span className="kiosk-playlist-name">{state.playlist_name}</span>
        </div>
        {nextPlaylistItem ? (
          <div className="kiosk-next-course">
            <span className="kiosk-next-course-label">{t("kiosk.nextCourseLabel")}</span>
            <span className="kiosk-next-course-title">{nextPlaylistItem.title}</span>
            <span className="kiosk-playlist-countdown-number" style={{ color: "var(--accent-text)" }}>
              {Math.ceil(state.playlist_waiting_remaining ?? 0)}
            </span>
          </div>
        ) : (
          <span className="kiosk-waiting-sub">{t("kiosk.playlistEnd")}</span>
        )}
      </div>

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
        <div
          className="coach-stage"
          style={{ "--coach-accent": programAccent } as React.CSSProperties}
        >
          <div className="coach-stage-glow" />
          <span className="coach-stage-eyebrow">{t("kiosk.coachModeLabel")}</span>
          <span className="coach-stage-course">{state.current_audio_course?.title}</span>
          {currentTrack ? (
            <>
              <span className="coach-stage-track-label">
                {t("kiosk.trackLabel", {
                  index: (state.audio_track_index ?? 0) + 1,
                  total: state.audio_tracks ? ` / ${state.audio_tracks.length}` : "",
                })}
              </span>
              <h1 className="coach-stage-track-title">{currentTrack.title}</h1>
              <div className="coach-stage-progress-track">
                <div className="coach-stage-progress-fill" style={{ transform: `scaleX(${audioTrackProgress / 100})` }} />
              </div>
              <div className="coach-stage-meta-row">
                <span className="coach-stage-time">{formatTime(state.audio_position_seconds)}</span>
                {!state.audio_playing && <span className="coach-stage-paused-badge">{t("kiosk.paused")}</span>}
                <span className="coach-stage-time">
                  {audioTrackRemaining !== null ? `-${formatTime(audioTrackRemaining)}` : "--:--"}
                </span>
              </div>
              {state.audio_chain_wait_remaining !== null && (
                <span className="coach-stage-next-hint">
                  {t("kiosk.nextTrackIn", { seconds: Math.ceil(state.audio_chain_wait_remaining ?? 0) })}
                </span>
              )}
            </>
          ) : (
            <span className="coach-stage-track-label">{t("kiosk.noTrack")}</span>
          )}
        </div>
      </div>

      {isPaused && (
        <div className="pause-overlay visible" onClick={() => sendCommand("play")}>
          <div className="pause-center" onClick={(e) => { e.stopPropagation(); }}>
            <div className="pause-media-col">
              <div
                className="pause-thumb-wrap"
                onClick={() => sendCommand("play")}
                title={t("kiosk.resume")}
              >
                {(() => {
                  const thumbSrc = getThumbnailSrc(state.current_video?.thumbnail_url || state.current_video?.thumbnail_path);
                  return thumbSrc ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={thumbSrc}
                      alt={state.current_video?.title || ""}
                      className="pause-thumb-img"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  ) : (
                    <div className="pause-thumb-fallback">
                      <AppLogo size={90} className="pause-logo" />
                    </div>
                  );
                })()}
                <div className="pause-thumb-overlay-btn">
                  <Icon name="play_arrow" size={48} filled />
                </div>
                <div className="pause-thumb-time">
                  {formatTime(state.position_seconds)} / {formatTime(duration)}
                </div>
              </div>

              <div className="pause-logo-mini-wrap">
                <AppLogo size={80} className="pause-logo" />
              </div>
            </div>

            <div className="pause-details-col">
              <div>
                <div className="pause-header-row">
                  <span className="pause-kicker" style={{ color: programAccent }}>
                    {t("kiosk.pausedLabel")}
                  </span>
                  {program && (
                    <span className="pause-badge" style={{ color: programAccent }}>
                      {program}
                    </span>
                  )}
                  {state.current_video?.release && (
                    <span className="pause-year">{state.current_video.release}</span>
                  )}
                  {getResolutionBadge(state.current_video?.width, state.current_video?.height, "HD") && (
                    <span className="pause-badge-pill">
                      {getResolutionBadge(state.current_video?.width, state.current_video?.height, "HD")}
                    </span>
                  )}
                  {getAudioQualityBadge(state.current_video?.audio_channels, state.current_video?.audio_codec, t("audioBadge.stereo"), t) && (
                    <span className="pause-badge-pill">
                      {getAudioQualityBadge(state.current_video?.audio_channels, state.current_video?.audio_codec, t("audioBadge.stereo"), t)}
                    </span>
                  )}
                </div>

                <h2 className="pause-title">{state.current_video?.title}</h2>
              </div>

              {state.current_video?.description ? (
                <div className="pause-description-scroll">
                  <p className="pause-description-text">{formatCleanDescription(state.current_video.description)}</p>
                </div>
              ) : (
                <div style={{ flex: 1 }} />
              )}

              <div className="pause-actions-row">
                <button
                  className="pause-resume-btn-pill"
                  onClick={() => sendCommand("play")}
                  title={t("kiosk.resume")}
                >
                  <Icon name="play_arrow" size={24} filled />
                  <span>{t("kiosk.resume")}</span>
                </button>
              </div>
            </div>
          </div>
          <div className="pause-progress-track">
            <div className="pause-progress-fill" style={{ transform: `scaleX(${pauseProgressPercent / 100})` }} />
          </div>
        </div>
      )}

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
