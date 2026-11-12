"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { CinemaRemoteState, PlaybackState } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import DisplayOutputSwitch from "@/components/DisplayOutputSwitch";
import RadioRemotePanel from "@/components/RadioRemotePanel";
import Icon from "@/components/Icon";
import CourseCard from "@/components/CourseCard";
import Sheet from "@/components/Sheet";
import SubtitlePicker from "@/components/SubtitlePicker";
import ChapterList from "@/components/ChapterList";
import ChapterTicks from "@/components/ChapterTicks";
import { useVideoChapters } from "@/lib/chapters";
import { courseThumbSrc, formatClock } from "@/lib/courseMeta";
import { formatCleanDescription } from "@/lib/formatDescription";
import { getAudioQualityBadge, getResolutionBadge } from "@/lib/videoBadges";
import type { DisplayOutput } from "@/lib/displayChannel";
import SearchBox from "@/components/SearchBox";
import { matchesQuery } from "@/lib/searchText";
import { formatTime } from "@/lib/format";

interface VideoSummary {
  id: number;
  title: string;
  program: string | null;
  release?: string | null;
  duration_seconds: number | null;
  thumbnail_path?: string | null;
  description?: string | null;
  width?: number | null;
  height?: number | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
}

interface PlaylistSummary {
  id: number;
  name: string;
  item_count: number;
}

interface BackgroundSummary {
  id: number;
  title: string;
  thumbnail_path?: string | null;
}

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
  const [launchSearch, setLaunchSearch] = useState("");
  const [launchTab, setLaunchTab] = useState<"videos" | "playlists" | "backgrounds">("videos");
  const [previewVideoId, setPreviewVideoId] = useState<number | null>(null);
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

  const closeLaunchSheet = () => {
    setSheet("none");
    setPreviewVideoId(null);
    setLaunchSearch("");
  };
  const previewVideo = previewVideoId !== null ? videos.find((v) => v.id === previewVideoId) ?? null : null;
  const releaseLabel = (release: string) => t("mobileRemote.releaseShort", { release });
  const kioskChapters = useVideoChapters(state.current_video?.id, getApiUrl);
  const cinemaChapters = useVideoChapters(cinemaLive?.video_id, getApiUrl);
  const cinemaVideo = cinemaLive?.video_id ? videos.find((v) => v.id === cinemaLive.video_id) ?? null : null;

  const launchSuggestions = [
    ...videos.flatMap((v) => (v.program ? [v.title, v.program] : [v.title])),
    ...playlists.map((p) => p.name),
    ...backgrounds.map((b) => b.title),
  ];
  const filteredVideos = videos.filter((v) => matchesQuery(`${v.title} ${v.program ?? ""}`, launchSearch));
  const filteredPlaylists = playlists.filter((p) => matchesQuery(p.name, launchSearch));
  const filteredBackgrounds = backgrounds.filter((b) => matchesQuery(b.title, launchSearch));

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

      <Sheet
        open={sheet !== "none"}
        onClose={closeLaunchSheet}
        tall
        closeLabel={t("mobileRemote.close")}
        title={previewVideo ? t("mobileRemote.preview") : t("mobileRemote.launchTitle")}
        header={
          previewVideo ? undefined : (
            <>
              <SearchBox
                className="search-input sheet-search"
                placeholder={t("mobileRemote.searchPlaceholder")}
                value={launchSearch}
                onChange={setLaunchSearch}
                suggestions={launchSuggestions}
              />
              <div className="view-toggle launch-tabs" style={{ marginTop: 10 }}>
                {(
                  [
                    ["videos", t("mobileRemote.tabCourses"), filteredVideos.length],
                    ["playlists", t("mobileRemote.tabPlaylists"), filteredPlaylists.length],
                    ["backgrounds", t("mobileRemote.tabBackgrounds"), filteredBackgrounds.length],
                  ] as const
                ).map(([key, label, count]) => (
                  <button key={key} type="button" className={`view-btn olc-press ${launchTab === key ? "active" : ""}`} onClick={() => setLaunchTab(key)}>
                    {label} <span style={{ opacity: 0.6 }}>{count}</span>
                  </button>
                ))}
              </div>
            </>
          )
        }
        footer={
          previewVideo ? (
            <>
              <button type="button" className="btn btn-secondary" onClick={() => setPreviewVideoId(null)}>
                {t("mobileRemote.back")}
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  sendCommand("load", { video_id: previewVideo.id });
                  closeLaunchSheet();
                }}
              >
                <Icon name="play_arrow" size={20} filled />
                {t("mobileRemote.launchNow")}
              </button>
            </>
          ) : undefined
        }
      >
        {previewVideo ? (
          <div className="launch-preview">
            <CourseCard
              variant="hero"
              getApiUrl={getApiUrl}
              releaseLabel={releaseLabel}
              fallbackProgram={t("mobileRemote.otherProgram")}
              course={previewVideo}
            />
            <div className="launch-preview__specs">
              {getResolutionBadge(previewVideo.width, previewVideo.height) && <span>{getResolutionBadge(previewVideo.width, previewVideo.height)}</span>}
              {getAudioQualityBadge(previewVideo.audio_channels, previewVideo.audio_codec, null, t) && (
                <span>{getAudioQualityBadge(previewVideo.audio_channels, previewVideo.audio_codec, null, t)}</span>
              )}
              {previewVideo.duration_seconds ? <span>{formatClock(previewVideo.duration_seconds)}</span> : null}
            </div>
            {previewVideo.description ? <p className="launch-preview__description">{formatCleanDescription(previewVideo.description)}</p> : null}
          </div>
        ) : (
          <>
            {launchTab === "videos" &&
              filteredVideos.map((v) => (
                <CourseCard
                  key={`v-${v.id}`}
                  getApiUrl={getApiUrl}
                  releaseLabel={releaseLabel}
                  fallbackProgram={t("mobileRemote.otherProgram")}
                  course={v}
                  onClick={() => setPreviewVideoId(v.id)}
                  trailing={<Icon name="chevron_right" size={20} style={{ alignSelf: "center", color: "var(--text-muted)" }} />}
                />
              ))}
            {launchTab === "playlists" &&
              filteredPlaylists.map((p) => (
                <button
                  key={`pl-${p.id}`}
                  type="button"
                  className="sheet-option olc-press"
                  onClick={() => {
                    sendCommand("load_playlist", { playlist_id: p.id });
                    closeLaunchSheet();
                  }}
                >
                  <Icon name="playlist_play" size={22} />
                  <span className="sheet-option__text">
                    <span className="sheet-option__label">{p.name}</span>
                    <span className="sheet-option__sub">{t("mobileRemote.coursesCount", { count: p.item_count })}</span>
                  </span>
                </button>
              ))}
            {launchTab === "backgrounds" &&
              filteredBackgrounds.map((b) => {
                const thumb = courseThumbSrc(getApiUrl, { thumbnail_path: b.thumbnail_path });
                return (
                  <button
                    key={`bg-${b.id}`}
                    type="button"
                    className="sheet-option olc-press"
                    onClick={() => {
                      sendCommand("load_background", { background_id: b.id });
                      closeLaunchSheet();
                    }}
                  >
                    {thumb ? <img className="sheet-option__thumb" src={thumb} alt="" loading="lazy" /> : <Icon name="gradient" size={22} />}
                    <span className="sheet-option__text">
                      <span className="sheet-option__label">{b.title}</span>
                      <span className="sheet-option__sub">{t("mobileRemote.backgroundLabel")}</span>
                    </span>
                  </button>
                );
              })}
            {((launchTab === "videos" && filteredVideos.length === 0) ||
              (launchTab === "playlists" && filteredPlaylists.length === 0) ||
              (launchTab === "backgrounds" && filteredBackgrounds.length === 0)) && <p className="live-empty">{t("mobileRemote.noResults")}</p>}
          </>
        )}
      </Sheet>
    </div>
  );
}
