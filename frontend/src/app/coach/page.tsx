"use client";

import React, { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { usePlaybackSocket, PlaybackState } from "@/lib/usePlaybackSocket";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { anchorPosition } from "@/lib/playbackClock";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import { formatTime } from "@/lib/format";
import AmbiancePalette from "@/components/coach/AmbiancePalette";
import CoachNavSheet from "@/components/coach/CoachNavSheet";
import CoachPicker from "@/components/coach/CoachPicker";
import CoachStageMonitor from "@/components/coach/CoachStageMonitor";
import TrackListSheet from "@/components/coach/TrackListSheet";
import type { AudioCourseSummary, AudioPlaylistSummary, BackgroundSummary } from "@/components/coach/types";

export default function CoachModePage() {
  const { t } = useAppSettings();
  const CHAIN_MODE_LABELS: Record<string, string> = {
    auto: t("coach.chainModeLabels.auto"),
    manual: t("coach.chainModeLabels.manual"),
  };
  const [hasSynced, setHasSynced] = useState(false);
  const { state: wsState, connected, sendCommand, serverNow } = usePlaybackSocket(() => setHasSynced(true), undefined, "cable", undefined, "coach");
  const [courses, setCourses] = useState<AudioCourseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [audioPlaylists, setAudioPlaylists] = useState<AudioPlaylistSummary[]>([]);
  const [showTrackList, setShowTrackList] = useState(false);
  const [backgrounds, setBackgrounds] = useState<BackgroundSummary[]>([]);
  const [showNav, setShowNav] = useState(false);
  const [snapshotState, setSnapshotState] = useState<PlaybackState | null>(null);
  const state = hasSynced ? wsState : (snapshotState ?? wsState);

  useEffect(() => {
    fetch(getApiUrl("/playback/state"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: PlaybackState | null) => {
        if (data && data.state) setSnapshotState(data);
      })
      .catch(() => { });
  }, []);

  useEffect(() => {
    fetch(getApiUrl("/audio"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setCourses)
      .catch(() => setCourses([]))
      .finally(() => setLoading(false));

    fetch(getApiUrl("/backgrounds"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setBackgrounds)
      .catch(() => setBackgrounds([]));

    fetch(getApiUrl("/audio-playlists"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : []))
      .then(setAudioPlaylists)
      .catch(() => setAudioPlaylists([]));
  }, []);

  const isCoachMode = state.state === "coach_mode";
  const course = state.current_audio_course;
  const accent = "var(--accent-primary)";
  const accentFg = useThemeAccentForeground();
  const tracks = state.audio_tracks || [];
  const trackIndex = state.audio_track_index ?? 0;
  const currentTrack = tracks[trackIndex] || null;

  const [anchoredPos, setLocalPos] = useState<number>(0);

  const audioAnchor = state.audio_clock;
  const trackDuration = currentTrack?.duration_seconds;
  useEffect(() => {
    if (!audioAnchor) return;
    const compute = () => {
      const position = anchorPosition(audioAnchor, serverNow());
      setLocalPos(trackDuration ? Math.min(position, trackDuration) : position);
    };
    compute();
    if (!audioAnchor.running) return;
    const timer = setInterval(compute, 100);
    return () => clearInterval(timer);
  }, [audioAnchor, trackDuration, serverNow]);
  const localPos = audioAnchor ? anchoredPos : state.audio_position_seconds || 0;

  const remaining = currentTrack?.duration_seconds
    ? Math.max(0, currentTrack.duration_seconds - localPos)
    : null;

  const launchCourse = (courseId: number) => {
    sendCommand("load_audio_course", { audio_course_id: courseId });
  };

  const launchAudioPlaylist = (playlistId: number) => {
    sendCommand("load_audio_playlist", { audio_playlist_id: playlistId });
  };

  const router = useRouter();

  const handleExitCoach = async () => {
    try {
      await sendCommand("stop");
    } finally {
      if (typeof window !== "undefined" && (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")) {
        router.push("/grid");
      } else {
        router.push("/");
      }
    }
  };

  const handleBackFromPicker = () => {
    if (typeof window !== "undefined" && (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")) {
      router.push("/grid");
    } else {
      router.push("/");
    }
  };

  const wasCoachModeRef = useRef(isCoachMode);
  useEffect(() => {
    if (wasCoachModeRef.current && !isCoachMode) {
      if (typeof window !== "undefined" && (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")) {
        router.replace("/grid");
      }
    }
    wasCoachModeRef.current = isCoachMode;
  }, [isCoachMode, router]);

  const navSheet = showNav && <CoachNavSheet t={t} onClose={() => setShowNav(false)} />;

  if (!isCoachMode) {
    return (
      <CoachPicker
        t={t} connected={connected} loading={loading} courses={courses} audioPlaylists={audioPlaylists}
        handleBackFromPicker={handleBackFromPicker} openNav={() => setShowNav(true)}
        launchCourse={launchCourse} launchAudioPlaylist={launchAudioPlaylist}
      >
        {navSheet}
      </CoachPicker>
    );
  }

  const activeBgId = state.current_background?.id ?? state.current_audio_course?.background_id ?? null;
  const activeBgTitle = state.current_background?.title ?? (
    activeBgId ? backgrounds.find((b) => b.id === activeBgId)?.title : null
  );
  const activeBgIsImage = state.current_background?.is_image ?? (
    activeBgId ? Boolean(backgrounds.find((b) => b.id === activeBgId)?.is_image) : false
  );
  const audioProgress = currentTrack?.duration_seconds && currentTrack.duration_seconds > 0
    ? Math.min(100, (localPos / currentTrack.duration_seconds) * 100)
    : 0;

  return (
    <div className="coach-screen coach-live-screen" style={{ borderTopColor: accent }}>
      <div className="coach-live-header" style={{ maxWidth: "1280px", justifyContent: "flex-end" }}>
        <button className="coach-icon-btn olc-press" onClick={() => setShowNav(true)} title={t("coach.otherFunctions")}>
          <Icon name="menu" size={20} />
        </button>
      </div>

      <div className="coach-console-grid">
        <div className="coach-audio-col">
          <div className="coach-live-track-block olc-anim-in" key={currentTrack?.id} style={{ width: "100%", maxWidth: "420px" }}>
            <span className="coach-live-track-label">
              {currentTrack ? t("coach.trackLabel", { index: trackIndex + 1, total: tracks.length }) : t("coach.noTrack")}
            </span>
            <span className="coach-live-track-title">{currentTrack?.title}</span>
            <span className="coach-live-track-time">- {formatTime(remaining)}</span>
            <div style={{ width: "100%", height: "6px", background: "var(--bg-surface-elevated)", borderRadius: "3px", overflow: "hidden", marginTop: "10px" }}>
              <div style={{ width: `${audioProgress}%`, height: "100%", background: accent, transition: "width 0.25s linear" }} />
            </div>
          </div>

          <div className="coach-controls-grid">
            <button className="coach-btn olc-press" onClick={() => sendCommand("audio_previous_track")} disabled={trackIndex <= 0} title={t("common.previous")}>
              <Icon name="skip_previous" size={28} filled />
            </button>
            <button
              className="coach-btn coach-btn-main olc-press"
              style={{ background: accent, color: accentFg }}
              onClick={() => sendCommand(state.audio_playing ? "pause" : "play")}
              title={state.audio_playing ? t("common.pause") : t("common.play")}
            >
              <Icon name={state.audio_playing ? "pause" : "play_arrow"} size={36} color={accentFg} filled />
            </button>
            <button
              className="coach-btn olc-press"
              onClick={() => sendCommand("audio_next_track")}
              disabled={trackIndex >= tracks.length - 1}
              title={t("common.next")}
            >
              <Icon name="skip_next" size={28} filled />
            </button>
          </div>

          <button className="coach-btn coach-btn-wide olc-press" onClick={() => sendCommand("audio_restart_track")}>
            <Icon name="restart_alt" size={18} />
            {t("coach.restartTrack")}
          </button>

          <div className="coach-volume-row">
            <button aria-label={t("common.volumeDown")} className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.max(0, state.volume - 10) })}>
              <Icon name="remove" size={18} />
            </button>
            <span className="coach-volume-value">
              <Icon name="volume_up" size={16} style={{ marginRight: "4px" }} />
              {state.volume}%
            </span>
            <button aria-label={t("common.volumeUp")} className="coach-btn coach-btn-square olc-press" onClick={() => sendCommand("volume", { volume: Math.min(100, state.volume + 10) })}>
              <Icon name="add" size={18} />
            </button>
          </div>

          <div className="coach-chain-mode-row">
            {(["auto", "manual"] as const).map((mode) => (
              <button
                key={mode}
                className={`speed-btn ${state.audio_chain_mode === mode ? "active" : ""}`}
                style={{ minHeight: "44px", flex: 1 }}
                onClick={() => sendCommand("audio_set_chain_mode", { mode })}
              >
                {CHAIN_MODE_LABELS[mode]}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="coach-btn coach-btn-wide olc-press"
            style={{ minHeight: "52px", marginTop: "4px" }}
            onClick={() => setShowTrackList(true)}
          >
            <Icon name="queue_music" size={20} />
            <span>{t("coach.viewTracks", { count: tracks.length })}</span>
          </button>

          <button
            type="button"
            className="coach-exit-btn-centered olc-press"
            onClick={handleExitCoach}
            title={t("coach.disableCoachMode")}
          >
            <Icon name="power_settings_new" size={20} />
            <span>{t("coach.exitMode")}</span>
          </button>
        </div>

        <div className="coach-stage-col">
          <CoachStageMonitor
            t={t} activeBgId={activeBgId} activeBgIsImage={activeBgIsImage} activeBgTitle={activeBgTitle}
            title={currentTrack?.title || course?.title}
            trackLabel={currentTrack ? t("coach.trackLabel", { index: trackIndex + 1, total: tracks.length }) : ""}
            localPos={localPos} duration={currentTrack?.duration_seconds} audioProgress={audioProgress} accent={accent}
          />
          <AmbiancePalette
            t={t} backgrounds={backgrounds} activeBgId={activeBgId}
            chooseBackground={(id) => sendCommand("audio_set_background", { background_id: id })}
          />
        </div>
      </div>

      {showTrackList && (
        <TrackListSheet
          t={t} tracks={tracks} trackIndex={trackIndex} onClose={() => setShowTrackList(false)}
          onJump={(index) => { sendCommand("audio_jump_to_track", { index }); setShowTrackList(false); }}
        />
      )}

      {navSheet}
    </div>
  );
}
