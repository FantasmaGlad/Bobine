"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { CinemaRemoteState, PlaybackState } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import DisplayOutputSwitch from "@/components/DisplayOutputSwitch";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import Icon from "@/components/Icon";
import CourseCard from "@/components/CourseCard";
import SubtitlePicker from "@/components/SubtitlePicker";
import ChapterList from "@/components/ChapterList";
import ChapterTicks from "@/components/ChapterTicks";
import { useVideoChapters } from "@/lib/chapters";
import type { DisplayOutput } from "@/lib/displayChannel";
import { formatTime } from "@/lib/format";
import LaunchSheet, { type BackgroundSummary, type PlaylistSummary, type VideoSummary } from "@/components/dashboard/LaunchSheet";

interface MobileRemoteProps {
  state: PlaybackState;
  livePosition: number;
  connected: boolean;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
  videos: VideoSummary[];
  playlists: PlaylistSummary[];
  backgrounds: BackgroundSummary[];
  getApiUrl: (path: string) => string;
  displayOutputCable: DisplayOutput | null;
  displayOutputNetwork: "kiosk" | "cinema" | null;
  cinemaLive: CinemaRemoteState | null;
  onCinemaPlayPause: () => void;
  onSetDisplayOutput: (channel: "cable" | "network", output: DisplayOutput) => void;
  channel?: "cable" | "network";
}

const STOP_HOLD_MS = 650;

export default function MobileRemote({
  state,
  livePosition,
  connected,
  sendCommand,
  videos,
  playlists,
  backgrounds,
  getApiUrl,
  displayOutputCable,
  displayOutputNetwork,
  cinemaLive,
  onCinemaPlayPause,
  onSetDisplayOutput,
  channel,
}: MobileRemoteProps) {
  const { t } = useAppSettings();
  const [sheet, setSheet] = useState<"none" | "launch">("none");
  const [holdingStop, setHoldingStop] = useState(false);
  const [seekDragValue, setSeekDragValue] = useState<number | null>(null);
  const [cinemaSeekDrag, setCinemaSeekDrag] = useState<number | null>(null);
  const stopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const channelCinema = (channel === "network" ? displayOutputNetwork : displayOutputCable) === "cinema";
  const channelRadio = channel !== "network" && displayOutputCable === "radio";

  useEffect(() => {
    if (channelCinema || channelRadio) setSheet("none");
  }, [channelCinema, channelRadio]);

  const isActive = state.current_video !== null || state.state === "playlist_waiting" || state.state === "background";
  const duration = state.current_video?.duration_seconds ?? 0;
  const displayPosition = seekDragValue ?? livePosition;

  const nextPlaylistItem =
    state.playlist_items && state.playlist_index !== null && state.playlist_index !== undefined
      ? state.playlist_items[state.playlist_index + 1]
      : null;

  const startStopHold = (e: React.PointerEvent<HTMLButtonElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setHoldingStop(true);
    stopTimerRef.current = setTimeout(() => {
      sendCommand("stop");
      setHoldingStop(false);
    }, STOP_HOLD_MS);
  };

  const cancelStopHold = () => {
    setHoldingStop(false);
    if (stopTimerRef.current) {
      clearTimeout(stopTimerRef.current);
      stopTimerRef.current = null;
    }
  };

  const releaseLabel = (release: string) => t("mobileRemote.releaseShort", { release });
  const kioskChapters = useVideoChapters(state.current_video?.id, getApiUrl);
  const cinemaChapters = useVideoChapters(cinemaLive?.video_id, getApiUrl);
  const cinemaVideo = cinemaLive?.video_id ? videos.find((v) => v.id === cinemaLive.video_id) ?? null : null;

  return (
    <div className="mobile-remote">
      {connected && (
        <div className="mobile-remote-output olc-anim-in">
          {(!channel || channel === "cable") && (
            <DisplayOutputSwitch
              displayOutput={displayOutputCable}
              onSetDisplayOutput={(output) => onSetDisplayOutput("cable", output)}
              label={t("dashboard.displayOutputCableLabel")}
              allowRadio
            />
          )}
          {(!channel || channel === "network") && (
            <DisplayOutputSwitch
              displayOutput={displayOutputNetwork}
              onSetDisplayOutput={(output) => onSetDisplayOutput("network", output)}
              label={t("dashboard.displayOutputNetworkLabel")}
            />
          )}
        </div>
      )}
      {!connected ? (
        <div className="mobile-remote-empty">{t("mobileRemote.connectingHint")}</div>
      ) : channelRadio ? (
        <RadioRemotePanel key="radio_cable" channel="radio_cable" variant="compact" />
      ) : channelCinema ? (
        cinemaLive ? (
          <>
            <div className="now-card olc-anim-in">
              <div className="now-card__label">
                <span className="is-live" />
                {t("mobileRemote.nowPlayingCinema")}
              </div>
              <CourseCard
                variant="hero"
                getApiUrl={getApiUrl}
                releaseLabel={releaseLabel}
                fallbackProgram={t("mobileRemote.otherProgram")}
                course={{
                  id: cinemaVideo?.id ?? cinemaLive.video_id ?? 0,
                  title: cinemaLive.title ?? cinemaVideo?.title ?? "",
                  program: cinemaVideo?.program ?? cinemaLive.program,
                  release: cinemaVideo?.release,
                  duration_seconds: cinemaLive.duration_seconds || cinemaVideo?.duration_seconds,
                  thumbnail_path: cinemaVideo?.thumbnail_path,
                }}
              />
              <div className="mobile-remote-progress">
                <div className="chapter-seek">
                <input
                  type="range"
                  min={0}
                  max={cinemaLive.duration_seconds || 0}
                  step={1}
                  value={cinemaSeekDrag ?? cinemaLive.position_seconds}
                  onChange={(e) => setCinemaSeekDrag(Number(e.target.value))}
                  onMouseUp={(e) => {
                    sendCommand("cinema_command", { action: "seek", position_seconds: Number((e.target as HTMLInputElement).value) });
                    setCinemaSeekDrag(null);
                  }}
                  onTouchEnd={(e) => {
                    sendCommand("cinema_command", { action: "seek", position_seconds: Number((e.target as HTMLInputElement).value) });
                    setCinemaSeekDrag(null);
                  }}
                  className="seek-slider mobile-remote-seek"
                />
                <ChapterTicks chapters={cinemaChapters} duration={cinemaLive.duration_seconds || 0} />
                </div>
                <div className="now-card__times">
                  <span>{formatTime(cinemaSeekDrag ?? cinemaLive.position_seconds)}</span>
                  <span>{formatTime(cinemaLive.duration_seconds)}</span>
                </div>
              </div>
              <ChapterList
                chapters={cinemaChapters}
                position={cinemaSeekDrag ?? cinemaLive.position_seconds}
                onSeek={(seconds) => sendCommand("cinema_command", { action: "seek", position_seconds: seconds })}
              />
            </div>

            <div className="mobile-remote-controls" style={{ marginTop: 0 }}>
              <button
                className="coach-btn coach-btn-main olc-press"
                style={{ background: "var(--accent-primary)" }}
                onClick={onCinemaPlayPause}
              >
                <Icon name={cinemaLive.playing ? "pause" : "play_arrow"} size={38} filled />
              </button>
            </div>

            <button
              className="coach-btn coach-btn-wide mobile-remote-stop olc-press"
              onClick={() => sendCommand("cinema_command", { action: "stop" })}
              title={t("dashboard.cinemaStopHint")}
            >
              <Icon name="stop_circle" size={18} />
              {t("dashboard.stop")}
            </button>
          </>
        ) : (
          <div className="mobile-remote-empty olc-anim-in">
            <p>{t("dashboard.cinemaNoPlayback")}</p>
          </div>
        )
      ) : !isActive ? (
        <div className="mobile-remote-empty olc-anim-in">
          <p>{t("mobileRemote.noCourseHint")}</p>
          <button className="btn btn-primary" style={{ height: "56px", marginTop: "16px" }} onClick={() => setSheet("launch")}>
            <Icon name="play_circle" size={20} />
            {t("mobileRemote.launchCourse")}
          </button>
        </div>
      ) : (
        <>
          <div className="now-card olc-anim-in">
            <div className="now-card__label">
              <span className="is-live" />
              {state.playlist_name ? state.playlist_name : t("mobileRemote.nowPlaying")}
            </div>
            {state.current_video ? (
              <CourseCard
                variant="hero"
                getApiUrl={getApiUrl}
                releaseLabel={releaseLabel}
                fallbackProgram={t("mobileRemote.otherProgram")}
                course={state.current_video}
              />
            ) : (
              <div className="mobile-remote-now">
                <span className="mobile-remote-title">{state.current_background?.title ?? ""}</span>
              </div>
            )}
            <div className="mobile-remote-progress">
              <div className="chapter-seek">
              <input
                type="range"
                min={0}
                max={duration || 0}
                step={1}
                value={displayPosition}
                disabled={state.state === "background"}
                onChange={(e) => setSeekDragValue(Number(e.target.value))}
                onMouseUp={(e) => {
                  sendCommand("seek", { position_seconds: Number((e.target as HTMLInputElement).value) });
                  setSeekDragValue(null);
                }}
                onTouchEnd={(e) => {
                  sendCommand("seek", { position_seconds: Number((e.target as HTMLInputElement).value) });
                  setSeekDragValue(null);
                }}
                className="seek-slider mobile-remote-seek"
              />
              <ChapterTicks chapters={kioskChapters} duration={duration} />
              </div>
              <div className="now-card__times">
                <span>{formatTime(displayPosition)}</span>
                <span>{formatTime(duration)}</span>
              </div>
            </div>
            <ChapterList chapters={kioskChapters} position={displayPosition} onSeek={(seconds) => sendCommand("seek", { position_seconds: seconds })} />
            {state.current_video && (
              <SubtitlePicker
                videoId={state.current_video.id}
                subtitle={state.subtitle}
                getApiUrl={getApiUrl}
                onChange={(subtitle) => sendCommand("set_subtitle", { subtitle })}
              />
            )}
            {nextPlaylistItem && state.state !== "playlist_waiting" && (
              <div className="now-card__next">
                {t("kiosk.nextCourseLabel")} {nextPlaylistItem.title}
              </div>
            )}
          </div>
        </>
      )}

      {!channelCinema && (
        <>
          <div className="mobile-remote-controls">
            <button
              className="coach-btn olc-press"
              onClick={() => sendCommand("previous_video")}
              disabled={state.playlist_index === null || state.playlist_index === 0}
            >
              <Icon name="skip_previous" size={28} filled />
            </button>
            <button
              className="coach-btn coach-btn-main olc-press"
              style={
                !isActive || state.state === "background"
                  ? undefined
                  : { background: "var(--accent-primary)", color: "var(--accent-primary-fg)" }
              }
              onClick={() => sendCommand(state.state === "playing" ? "pause" : "play")}
              disabled={!isActive || state.state === "background"}
            >
              <Icon name={state.state === "playing" ? "pause" : "play_arrow"} size={38} filled />
            </button>
            <button
              className="coach-btn olc-press"
              onClick={() => sendCommand("next_video")}
              disabled={state.playlist_items === null || state.playlist_index === (state.playlist_items?.length ?? 1) - 1}
            >
              <Icon name="skip_next" size={28} filled />
            </button>
          </div>

          <button
            className={`coach-btn coach-btn-wide mobile-remote-stop olc-press ${holdingStop ? "holding" : ""}`}
            style={{ touchAction: "none" }}
            disabled={!isActive}
            title={!isActive ? t("mobileRemote.noCourseHint") : undefined}
            onPointerDown={startStopHold}
            onPointerUp={cancelStopHold}
            onPointerCancel={cancelStopHold}
            onContextMenu={(e) => e.preventDefault()}
          >
            <Icon name="stop_circle" size={18} />
            {holdingStop ? t("mobileRemote.holdToStop") : t("mobileRemote.stopHoldLabel")}
          </button>

          <div className="coach-volume-row" style={{ maxWidth: "none" }}>
            <button className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.max(0, state.volume - 10) })}>
              <Icon name="remove" size={20} />
            </button>
            <span className="coach-volume-value">
              <Icon name="volume_up" size={18} style={{ marginRight: "6px" }} />
              {state.volume}%
            </span>
            <button className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.min(100, state.volume + 10) })}>
              <Icon name="add" size={20} />
            </button>
          </div>

          <div className="mobile-remote-quick-row">
            {isActive && (
              <button className="btn btn-secondary mobile-remote-quick-btn" onClick={() => setSheet("launch")}>
                <Icon name="play_circle" size={18} />
                {t("mobileRemote.launchQuickBtn")}
              </button>
            )}
            {channel !== "network" && (
              <Link href="/coach/" className="btn btn-primary mobile-remote-quick-btn" style={{ textDecoration: "none" }}>
                <Icon name="mic" size={18} />
                {t("mobileRemote.coachQuickBtn")}
              </Link>
            )}
          </div>

          <a
            href={`/schedule/?channel=${channel ?? "cable"}`}
            className="btn btn-secondary"
            style={{ textDecoration: "none", width: "100%", minHeight: "50px", flexShrink: 0, marginTop: "4px" }}
          >
            <Icon name="calendar_month" size={18} />
            {t("dashboard.viewSchedule")}
          </a>
        </>
      )}

      <LaunchSheet
        t={t} open={sheet !== "none"} onClose={() => setSheet("none")}
        videos={videos} playlists={playlists} backgrounds={backgrounds} getApiUrl={getApiUrl} sendCommand={sendCommand}
      />
    </div>
  );
}
