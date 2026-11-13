"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useInterpolatedPosition } from "@/lib/useInterpolatedPosition";
import { RadioEvent, RadioTrackInfo, selectRadioTarget, useRadioSocket } from "@/lib/useRadioSocket";
import { useMediaClockFollower } from "@/lib/useMediaClockFollower";
import { radioChannelId } from "@/lib/displayChannel";
import { createSoundChain, type SoundChain } from "@/lib/radioSoundGraph";
import { createMixStage, type MixStage } from "@/lib/radioMixGraph";
import { clampMix, defaultMix } from "@/lib/radioMix";
import { defaultSound } from "@/lib/radioSound";
import { useAudioRoute } from "@/lib/useAudioRoute";
import { detectAutoplayAllowed } from "@/lib/autoplayProbe";
import { getDisplayChannel, useDisplayOutputRedirect } from "@/lib/useDisplayOutputRedirect";
import Icon from "@/components/Icon";
import { getApiUrl } from "@/lib/apiUrl";
import { unloadMedia } from "@/lib/mediaElement";
import NowPlaying from "@/components/radio/NowPlaying";
import UnlockOverlay from "@/components/radio/UnlockOverlay";
import { useAudioContextKeepAlive } from "@/components/radio/useAudioContextKeepAlive";
import { useDuckSettings } from "@/components/radio/useDuckSettings";
import { useServerClock } from "@/components/radio/useServerClock";
import { useLevelMeter } from "@/components/radio/useLevelMeter";
import { useRadioRemote } from "@/components/radio/useRadioRemote";

type Slot = 0 | 1;
const OTHER_SLOT = (slot: Slot): Slot => (slot === 0 ? 1 : 0);

export default function RadioScreenPage() {
  const { t } = useAppSettings();

  const audioARef = useRef<HTMLAudioElement | null>(null);
  const audioBRef = useRef<HTMLAudioElement | null>(null);
  const announcementAudioRef = useRef<HTMLAudioElement | null>(null);
  const getAudioEl = (slot: Slot): HTMLAudioElement | null => (slot === 0 ? audioARef.current : audioBRef.current);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const gainARef = useRef<GainNode | null>(null);
  const gainBRef = useRef<GainNode | null>(null);
  const getGain = (slot: Slot): GainNode | null => (slot === 0 ? gainARef.current : gainBRef.current);
  const setGainRef = (slot: Slot, node: GainNode) => {
    if (slot === 0) gainARef.current = node;
    else gainBRef.current = node;
  };
  const announcementGainRef = useRef<GainNode | null>(null);
  const graphReadyRef = useRef(false);
  const soundChainRef = useRef<SoundChain | null>(null);
  const soundRef = useRef(defaultSound());
  const mixStageRef = useRef<MixStage | null>(null);
  const mixRef = useRef(defaultMix());
  const [graphReady, setGraphReady] = useState(false);

  const [unlocked, setUnlocked] = useState(false);
  const [lastCause, setLastCause] = useState("sync");
  const lastReportRef = useRef(0);
  const isPrimaryRef = useRef(false);

  const activeSlotRef = useRef<Slot>(0);
  const slotTrackIdRef = useRef<[number | null, number | null]>([null, null]);
  const crossfadingRef = useRef(false);

  const lastProgressRef = useRef<[number, number]>([0, 0]);
  const recoveringRef = useRef(false);
  const unlockedRef = useRef(false);
  const playingRef = useRef(false);

  const activeAnnouncementRef = useRef<{ id: number; mode: string } | null>(null);
  const announcementFadeOutTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recoveryPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const duckSettingsRef = useDuckSettings();

  const ensureAudioGraph = (initialVolume: number) => {
    if (graphReadyRef.current) return;
    const AudioContextClass =
      window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    audioCtxRef.current = ctx;
    const mixStage = createMixStage(ctx, ctx.destination, mixRef.current);
    mixStageRef.current = mixStage;
    const soundChain = createSoundChain(ctx, mixStage.musicInput, soundRef.current);
    soundChainRef.current = soundChain;
    for (const slot of [0, 1] as Slot[]) {
      const el = getAudioEl(slot);
      if (!el) continue;
      el.volume = 1;
      const gain = ctx.createGain();
      gain.gain.value = slot === activeSlotRef.current ? initialVolume / 100 : 0;
      gain.connect(soundChain.input);
      ctx.createMediaElementSource(el).connect(gain);
      setGainRef(slot, gain);
    }
    const annEl = announcementAudioRef.current;
    if (annEl) {
      annEl.volume = 1;
      const annGain = ctx.createGain();
      annGain.gain.value = 1;
      annGain.connect(mixStage.announcementsInput);
      ctx.createMediaElementSource(annEl).connect(annGain);
      announcementGainRef.current = annGain;
    }
    graphReadyRef.current = true;
    setGraphReady(true);
  };

  const setGainNow = (slot: Slot, value: number) => {
    const gain = getGain(slot);
    const ctx = audioCtxRef.current;
    if (!gain || !ctx) return;
    gain.gain.cancelScheduledValues(ctx.currentTime);
    gain.gain.setValueAtTime(value, ctx.currentTime);
  };

  const rampGain = (slot: Slot, to: number, durationMs: number) => {
    const gain = getGain(slot);
    const ctx = audioCtxRef.current;
    if (!gain || !ctx) return;
    const now = ctx.currentTime;
    gain.gain.cancelScheduledValues(now);
    gain.gain.setValueAtTime(gain.gain.value, now);
    gain.gain.linearRampToValueAtTime(to, now + Math.max(0.001, durationMs / 1000));
  };

  const loadDirect = (track: RadioTrackInfo, positionSeconds: number, playing: boolean, volumePercent: number) => {
    const slot = activeSlotRef.current;
    const el = getAudioEl(slot);
    if (!el) return;
    slotTrackIdRef.current[slot] = track.id;
    lastProgressRef.current[slot] = Date.now();
    el.src = getApiUrl(`/radio/tracks/${track.id}/stream`);
    el.load();
    setGainNow(slot, volumePercent / 100);
    const onReady = () => {
      el.removeEventListener("canplay", onReady);
      try {
        el.currentTime = positionSeconds || 0;
      } catch {
      }
      if (playing && unlocked) el.play().catch(() => {});
    };
    el.addEventListener("canplay", onReady);
  };

  const startCrossfade = (nextTrack: RadioTrackInfo, volumePercent: number, crossfadeSeconds: number) => {
    if (crossfadingRef.current) return;
    const fromSlot = activeSlotRef.current;
    const toSlot = OTHER_SLOT(fromSlot);
    const toEl = getAudioEl(toSlot);
    if (!toEl || !audioCtxRef.current) return;
    crossfadingRef.current = true;
    slotTrackIdRef.current[toSlot] = nextTrack.id;
    lastProgressRef.current[toSlot] = Date.now();
    toEl.src = getApiUrl(`/radio/tracks/${nextTrack.id}/stream`);
    toEl.currentTime = 0;
    setGainNow(toSlot, 0);
    toEl.play().catch(() => {});
    const durationMs = Math.max(200, crossfadeSeconds * 1000);
    rampGain(fromSlot, 0, durationMs);
    rampGain(toSlot, volumePercent / 100, durationMs);
  };

  const abortCrossfadeIfAny = (restoreVolumePercent: number) => {
    if (!crossfadingRef.current) return;
    const otherSlot = OTHER_SLOT(activeSlotRef.current);
    getAudioEl(otherSlot)?.pause();
    setGainNow(otherSlot, 0);
    setGainNow(activeSlotRef.current, restoreVolumePercent / 100);
    slotTrackIdRef.current[otherSlot] = null;
    crossfadingRef.current = false;
  };

  const handleEvent = (evt: RadioEvent) => {
    setLastCause(evt.cause);
    const data = evt.data;
    const announcementAudio = announcementAudioRef.current;

    const ann = data.current_announcement;
    const wasAnnouncing = activeAnnouncementRef.current;
    if (announcementAudio && ann && ann.id !== wasAnnouncing?.id) {
      activeAnnouncementRef.current = { id: ann.id, mode: ann.mode };
      abortCrossfadeIfAny(data.volume);
      if (announcementFadeOutTimeoutRef.current) {
        clearTimeout(announcementFadeOutTimeoutRef.current);
        announcementFadeOutTimeoutRef.current = null;
      }
      announcementAudio.src = getApiUrl(`/radio/announcements/${ann.id}/stream`);
      announcementAudio.load();
      if (unlocked) announcementAudio.play().catch(() => {});
      const fadeMs = duckSettingsRef.current.fadeMs;
      const annGain = announcementGainRef.current;
      const ctx = audioCtxRef.current;
      if (annGain && ctx) {
        annGain.gain.cancelScheduledValues(ctx.currentTime);
        annGain.gain.setValueAtTime(0, ctx.currentTime);
        annGain.gain.linearRampToValueAtTime(1, ctx.currentTime + Math.max(0.001, fadeMs / 1000));
      }
      if (ann.mode === "duck") {
        rampGain(activeSlotRef.current, duckSettingsRef.current.level / 100, fadeMs);
      }
    } else if (announcementAudio && !ann && wasAnnouncing) {
      activeAnnouncementRef.current = null;
      const fadeMs = duckSettingsRef.current.fadeMs;
      const annGain = announcementGainRef.current;
      const ctx = audioCtxRef.current;
      if (annGain && ctx) {
        annGain.gain.cancelScheduledValues(ctx.currentTime);
        annGain.gain.setValueAtTime(annGain.gain.value, ctx.currentTime);
        annGain.gain.linearRampToValueAtTime(0, ctx.currentTime + Math.max(0.001, fadeMs / 1000));
      }
      announcementFadeOutTimeoutRef.current = setTimeout(() => {
        unloadMedia(announcementAudio);
        announcementFadeOutTimeoutRef.current = null;
      }, fadeMs);
      if (wasAnnouncing.mode === "duck") {
        rampGain(activeSlotRef.current, data.volume / 100, fadeMs);
      }
    }
    const isDucking = activeAnnouncementRef.current?.mode === "duck";

    const track = data.current_track;
    if (!track) {
      for (const slot of [0, 1] as Slot[]) {
        const el = getAudioEl(slot);
        unloadMedia(el);
        slotTrackIdRef.current[slot] = null;
      }
      crossfadingRef.current = false;
      return;
    }

    const activeSlot = activeSlotRef.current;
    const otherSlot = OTHER_SLOT(activeSlot);

    if (track.id === slotTrackIdRef.current[activeSlot]) {
      const el = getAudioEl(activeSlot);
      if (!el) return;
      if (!isDucking) setGainNow(activeSlot, data.volume / 100);

      if (evt.cause === "radio_seek" || evt.cause === "radio_restart_track") {
        try {
          el.currentTime = data.position_seconds;
        } catch {
        }
      }

      if (ann?.mode === "wait_end") {
      } else if (data.playing && el.paused) {
        if (unlocked) el.play().catch(() => {});
      } else if (!data.playing && !el.paused) {
        el.pause();
      }
      return;
    }

    if (crossfadingRef.current && slotTrackIdRef.current[otherSlot] === track.id) {
      setGainNow(activeSlot, 0);
      setGainNow(otherSlot, isDucking ? duckSettingsRef.current.level / 100 : data.volume / 100);
      getAudioEl(activeSlot)?.pause();
      activeSlotRef.current = otherSlot;
      crossfadingRef.current = false;
      const newEl = getAudioEl(otherSlot);
      if (newEl && !data.playing && !newEl.paused) newEl.pause();
      return;
    }

    abortCrossfadeIfAny(data.volume);
    loadDirect(track, data.position_seconds || 0, data.playing, isDucking ? duckSettingsRef.current.level : data.volume);
  };

  const [displayChannel] = useState(() => getDisplayChannel("radio"));
  const radioChannel = radioChannelId(displayChannel);
  const { state, connected, sendCommand, isPrimary, serverNow, displayOutputCable } = useRadioSocket(
    handleEvent,
    "kiosk",
    radioChannel,
  );
  const soundKey = JSON.stringify(state.sound);
  useEffect(() => {
    soundRef.current = state.sound;
    soundChainRef.current?.apply(state.sound);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `soundKey` résume le contenu de state.sound
  }, [soundKey]);
  const mixKey = JSON.stringify(state.mix);
  useEffect(() => {
    mixRef.current = clampMix(state.mix);
    mixStageRef.current?.apply(mixRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `mixKey` résume le contenu de state.mix
  }, [mixKey]);
  useAudioRoute({ ctxRef: audioCtxRef, stageRef: mixStageRef, route: state.route ?? null, ready: graphReady, connected, sendCommand });
  useLevelMeter(mixStageRef, graphReady, Boolean(state.meter), isPrimary, sendCommand);
  useDisplayOutputRedirect("radio", displayOutputCable, null);
  const activeMediaRef = useMemo(
    () => ({ get current() { return getAudioEl(activeSlotRef.current); } }),
    [],
  );
  useMediaClockFollower({
    mediaRef: activeMediaRef,
    state,
    select: selectRadioTarget,
    enabled: !isPrimary,
    serverNow,
    tryPlay: (el) => {
      if (unlockedRef.current) el?.play().catch(() => {});
    },
  });
  useEffect(() => {
    isPrimaryRef.current = isPrimary;
  }, [isPrimary]);
  useEffect(() => {
    unlockedRef.current = unlocked;
  }, [unlocked]);
  useEffect(() => {
    playingRef.current = state.playing;
  }, [state.playing]);

  const livePosition = useInterpolatedPosition(state.position_seconds, state.playing, lastCause);

  const now = useServerClock();

  useEffect(() => {
    const slotA = audioARef;
    const slotB = audioBRef;
    const announcement = announcementAudioRef;
    return () => {
      if (announcementFadeOutTimeoutRef.current) clearTimeout(announcementFadeOutTimeoutRef.current);
      if (recoveryPollRef.current) clearInterval(recoveryPollRef.current);
      unloadMedia(slotA.current);
      unloadMedia(slotB.current);
      unloadMedia(announcement.current);
      audioCtxRef.current?.close().catch(() => {});
    };
  }, []);

  const maybeStartCrossfade = (el: HTMLAudioElement) => {
    if (crossfadingRef.current || !graphReadyRef.current || activeAnnouncementRef.current) return;
    if (state.repeat === "track") return;
    const { duration, currentTime } = el;
    if (!isFinite(duration) || duration <= 0) return;
    const crossfadeSeconds = Math.max(0, state.crossfade_seconds || 0);
    if (crossfadeSeconds <= 0 || duration - currentTime > crossfadeSeconds) return;

    const { order, index } = state;
    if (index === null) return;
    let nextTrack: RadioTrackInfo | null = null;
    if (index + 1 < order.length) nextTrack = order[index + 1];
    else if (state.repeat === "playlist" && order.length > 0) nextTrack = order[0];
    if (!nextTrack) return;

    startCrossfade(nextTrack, state.volume, crossfadeSeconds);
  };

  const handleTimeUpdateForSlot = (slot: Slot) => {
    const el = getAudioEl(slot);
    if (!el || slot !== activeSlotRef.current) return;
    lastProgressRef.current[slot] = Date.now();
    if (isPrimaryRef.current) {
      const nowMs = Date.now();
      if (nowMs - lastReportRef.current >= 900) {
        lastReportRef.current = nowMs;
        sendCommand("report_position", { position_seconds: el.currentTime });
      }
    }
    maybeStartCrossfade(el);
  };
  const handleTimeUpdateA = () => handleTimeUpdateForSlot(0);
  const handleTimeUpdateB = () => handleTimeUpdateForSlot(1);

  const handleEndedForSlot = (slot: Slot) => {
    if (slot === activeSlotRef.current) sendCommand("radio_track_ended", { track_id: slotTrackIdRef.current[slot] });
  };
  const handleEndedA = () => handleEndedForSlot(0);
  const handleEndedB = () => handleEndedForSlot(1);

  const RECOVERY_GRACE_MS = 10000;
  const RECOVERY_POLL_MS = 1000;

  const attemptRecovery = useCallback((slot: Slot) => {
    if (recoveringRef.current || slot !== activeSlotRef.current) return;
    recoveringRef.current = true;
    const el = getAudioEl(slot);
    if (el) {
      const pos = el.currentTime;
      try {
        el.load();
        el.currentTime = pos;
      } catch {
      }
      if (unlockedRef.current) el.play().catch(() => {});
    }
    const attemptStartedAt = Date.now();
    lastProgressRef.current[slot] = attemptStartedAt;
    if (recoveryPollRef.current) clearInterval(recoveryPollRef.current);
    const pollId = setInterval(() => {
      if (lastProgressRef.current[slot] > attemptStartedAt) {
        clearInterval(pollId);
        recoveringRef.current = false;
        return;
      }
      if (Date.now() - attemptStartedAt < RECOVERY_GRACE_MS) return;
      clearInterval(pollId);
      recoveringRef.current = false;
      if (slot === activeSlotRef.current && playingRef.current && !activeAnnouncementRef.current) {
        sendCommand("radio_track_ended", { track_id: slotTrackIdRef.current[slot] });
      }
    }, RECOVERY_POLL_MS);
    recoveryPollRef.current = pollId;
  }, [sendCommand]);

  const handleErrorForSlot = (slot: Slot) => {
    if (slot === activeSlotRef.current) {
      attemptRecovery(slot);
    } else if (crossfadingRef.current) {
      abortCrossfadeIfAny(state.volume);
    }
  };
  const handleErrorA = () => handleErrorForSlot(0);
  const handleErrorB = () => handleErrorForSlot(1);

  const STALL_TIMEOUT_MS = 15000;
  useEffect(() => {
    const id = setInterval(() => {
      if (!playingRef.current || activeAnnouncementRef.current || recoveringRef.current) return;
      const slot = activeSlotRef.current;
      if (Date.now() - lastProgressRef.current[slot] > STALL_TIMEOUT_MS) {
        attemptRecovery(slot);
      }
    }, 5000);
    return () => clearInterval(id);
  }, [attemptRecovery]);

  useAudioContextKeepAlive(audioCtxRef, unlockedRef);

  const handleUnlock = () => {
    setUnlocked(true);
    ensureAudioGraph(state.volume);
    audioCtxRef.current?.resume().catch(() => {});
    const radioIsActive = !!state.current_track && state.state !== "idle";
    const el = getAudioEl(activeSlotRef.current);
    if (el && radioIsActive && state.playing) {
      el.play().catch(() => {});
    }
    const announcementAudio = announcementAudioRef.current;
    if (announcementAudio && radioIsActive && state.current_announcement) {
      announcementAudio.play().catch(() => {});
    }
  };

  const [autoplayProbed, setAutoplayProbed] = useState(false);
  const handleUnlockRef = useRef<() => void>(() => {});
  useEffect(() => {
    handleUnlockRef.current = handleUnlock;
  });
  useEffect(() => {
    let cancelled = false;
    detectAutoplayAllowed().then((allowed) => {
      if (cancelled) return;
      if (allowed && !unlockedRef.current) handleUnlockRef.current();
      setAutoplayProbed(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const currentTrack = state.current_track;

  const handlePlayPause = () => sendCommand(state.playing ? "pause" : "play");

  useRadioRemote({ unlocked, hasTrack: Boolean(currentTrack), volume: state.volume, handleUnlock, handlePlayPause, sendCommand });

  return (
    <div className="radio-screen">
      <audio ref={audioARef} onTimeUpdate={handleTimeUpdateA} onEnded={handleEndedA} onError={handleErrorA} />
      <audio ref={audioBRef} onTimeUpdate={handleTimeUpdateB} onEnded={handleEndedB} onError={handleErrorB} />
      <audio ref={announcementAudioRef} onEnded={() => sendCommand("announcement_ended")} />

      {state.current_announcement && (
        <div className="radio-announcement-banner">
          <Icon name="campaign" size={18} />
          {state.current_announcement.description}
        </div>
      )}

      {autoplayProbed && !unlocked && <UnlockOverlay t={t} onUnlock={handleUnlock} />}

      <NowPlaying
        t={t} state={state} connected={connected} now={now} livePosition={livePosition}
        sendCommand={sendCommand} handlePlayPause={handlePlayPause}
      />
    </div>
  );
}
