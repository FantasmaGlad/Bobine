"use client";

import React, { useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useThemeAccentForeground } from "@/lib/useThemeAccentForeground";
import type { PlaybackState } from "@/lib/usePlaybackSocket";
import Icon from "@/components/Icon";
import AmbiancePalette from "@/components/coach/AmbiancePalette";
import CoachNavSheet from "@/components/coach/CoachNavSheet";
import CoachPicker from "@/components/coach/CoachPicker";
import CoachSettingsRows from "@/components/coach/CoachSettingsRows";
import CoachStageMonitor from "@/components/coach/CoachStageMonitor";
import CoachTrackBlock from "@/components/coach/CoachTrackBlock";
import CoachTransport from "@/components/coach/CoachTransport";
import TrackListSheet from "@/components/coach/TrackListSheet";
import type { BackgroundSummary } from "@/components/coach/types";
import { useCoachLibrary, useCoachState, useTrackPosition } from "@/components/coach/useCoachData";
import { useCoachNavigation } from "@/components/coach/useCoachNavigation";

function activeBackground(state: PlaybackState, backgrounds: BackgroundSummary[]) {
  const activeBgId = state.current_background?.id ?? state.current_audio_course?.background_id ?? null;
  const activeBgTitle = state.current_background?.title ?? (
    activeBgId ? backgrounds.find((b) => b.id === activeBgId)?.title : null
  );
  const activeBgIsImage = state.current_background?.is_image ?? (
    activeBgId ? Boolean(backgrounds.find((b) => b.id === activeBgId)?.is_image) : false
  );
  return { activeBgId, activeBgTitle, activeBgIsImage };
}

export default function CoachModePage() {
  const { t } = useAppSettings();
  const { state, connected, sendCommand, serverNow } = useCoachState();
  const { courses, loading, audioPlaylists, backgrounds } = useCoachLibrary();
  const [showTrackList, setShowTrackList] = useState(false);
  const [showNav, setShowNav] = useState(false);
  const isCoachMode = state.state === "coach_mode";
  const accent = "var(--accent-primary)";
  const accentFg = useThemeAccentForeground();
  const tracks = state.audio_tracks || [];
  const trackIndex = state.audio_track_index ?? 0;
  const currentTrack = tracks[trackIndex] || null;
  const localPos = useTrackPosition(state, serverNow, currentTrack?.duration_seconds);
  const remaining = currentTrack?.duration_seconds ? Math.max(0, currentTrack.duration_seconds - localPos) : null;
  const { handleExitCoach, handleBackFromPicker } = useCoachNavigation(isCoachMode, () => sendCommand("stop"));
  const navSheet = showNav && <CoachNavSheet t={t} onClose={() => setShowNav(false)} />;

  if (!isCoachMode) {
    return (
      <CoachPicker
        t={t} connected={connected} loading={loading} courses={courses} audioPlaylists={audioPlaylists}
        handleBackFromPicker={handleBackFromPicker} openNav={() => setShowNav(true)}
        launchCourse={(courseId) => sendCommand("load_audio_course", { audio_course_id: courseId })}
        launchAudioPlaylist={(playlistId) => sendCommand("load_audio_playlist", { audio_playlist_id: playlistId })}
      >
        {navSheet}
      </CoachPicker>
    );
  }

  const { activeBgId, activeBgTitle, activeBgIsImage } = activeBackground(state, backgrounds);
  const audioProgress = currentTrack?.duration_seconds && currentTrack.duration_seconds > 0
    ? Math.min(100, (localPos / currentTrack.duration_seconds) * 100)
    : 0;
  const trackLabel = currentTrack ? t("coach.trackLabel", { index: trackIndex + 1, total: tracks.length }) : "";

  return (
    <div className="coach-screen coach-live-screen" style={{ borderTopColor: accent }}>
      <div className="coach-live-header" style={{ maxWidth: "1280px", justifyContent: "flex-end" }}>
        <button className="coach-icon-btn olc-press" onClick={() => setShowNav(true)} title={t("coach.otherFunctions")}>
          <Icon name="menu" size={20} />
        </button>
      </div>
      <div className="coach-console-grid">
        <div className="coach-audio-col">
          <CoachTrackBlock key={currentTrack?.id} label={currentTrack ? trackLabel : t("coach.noTrack")} title={currentTrack?.title}
            remaining={remaining} audioProgress={audioProgress} accent={accent} />
          <CoachTransport t={t} state={state} sendCommand={sendCommand} trackIndex={trackIndex} trackCount={tracks.length} accent={accent} accentFg={accentFg} />
          <CoachSettingsRows t={t} state={state} sendCommand={sendCommand} />
          <button type="button" className="coach-btn coach-btn-wide olc-press" style={{ minHeight: "52px", marginTop: "4px" }} onClick={() => setShowTrackList(true)}>
            <Icon name="queue_music" size={20} />
            <span>{t("coach.viewTracks", { count: tracks.length })}</span>
          </button>
          <button type="button" className="coach-exit-btn-centered olc-press" onClick={handleExitCoach} title={t("coach.disableCoachMode")}>
            <Icon name="power_settings_new" size={20} />
            <span>{t("coach.exitMode")}</span>
          </button>
        </div>
        <div className="coach-stage-col">
          <CoachStageMonitor
            t={t} activeBgId={activeBgId} activeBgIsImage={activeBgIsImage} activeBgTitle={activeBgTitle}
            title={currentTrack?.title || state.current_audio_course?.title} trackLabel={trackLabel}
            localPos={localPos} duration={currentTrack?.duration_seconds} audioProgress={audioProgress} accent={accent}
          />
          <AmbiancePalette t={t} backgrounds={backgrounds} activeBgId={activeBgId}
            chooseBackground={(id) => sendCommand("audio_set_background", { background_id: id })} />
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
