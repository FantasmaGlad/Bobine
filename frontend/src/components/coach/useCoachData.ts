"use client";

import { useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { anchorPosition } from "@/lib/playbackClock";
import { usePlaybackSocket, type PlaybackState } from "@/lib/usePlaybackSocket";
import type { AudioCourseSummary, AudioPlaylistSummary, BackgroundSummary } from "./types";
import { WIRED_OUTPUT } from "@/lib/outputs";

function getList<T>(path: string, set: (value: T[]) => void) {
  return fetch(getApiUrl(path), { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : []))
    .then(set)
    .catch(() => set([]));
}

export function useCoachState() {
  const [hasSynced, setHasSynced] = useState(false);
  const socket = usePlaybackSocket(() => setHasSynced(true), undefined, WIRED_OUTPUT, undefined, "coach");
  const [snapshotState, setSnapshotState] = useState<PlaybackState | null>(null);

  useEffect(() => {
    fetch(getApiUrl(`/outputs/${WIRED_OUTPUT}`), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((output: { playback: PlaybackState } | null) => {
        if (output?.playback?.state) setSnapshotState(output.playback);
      })
      .catch(() => { });
  }, []);

  const state = hasSynced ? socket.state : (snapshotState ?? socket.state);
  return { state, connected: socket.connected, sendCommand: socket.sendCommand, serverNow: socket.serverNow };
}

export function useCoachLibrary() {
  const [courses, setCourses] = useState<AudioCourseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [audioPlaylists, setAudioPlaylists] = useState<AudioPlaylistSummary[]>([]);
  const [backgrounds, setBackgrounds] = useState<BackgroundSummary[]>([]);

  useEffect(() => {
    void getList("/audio", setCourses).finally(() => setLoading(false));
    void getList("/backgrounds", setBackgrounds);
    void getList("/audio-playlists", setAudioPlaylists);
  }, []);

  return { courses, loading, audioPlaylists, backgrounds };
}

export function useTrackPosition(state: PlaybackState, serverNow: () => number, trackDuration: number | null | undefined) {
  const [anchoredPos, setLocalPos] = useState<number>(0);
  const audioAnchor = state.audio_clock;
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
  return audioAnchor ? anchoredPos : state.audio_position_seconds || 0;
}
