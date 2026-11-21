"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useInterpolatedPosition } from "@/lib/useInterpolatedPosition";
import { RadioEvent, RadioTrackInfo, selectRadioTarget, useRadioSocket, type RadioState } from "@/lib/useRadioSocket";
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
import { useLevelMeter } from "@/components/radio/useLevelMeter";
import { useRadioRemote } from "@/components/radio/useRadioRemote";
import { rampParam, rampParamFrom, setParamNow } from "@/components/radio/engine/params";
import { crossfadeDurationMs, crossfadeSeconds, crossfadeTarget } from "@/components/radio/engine/crossfade";
import { decideTrack, otherSlot, targetGain, transportAction, type Slot } from "@/components/radio/engine/trackSync";
import { planAnnouncement, type ActiveAnnouncement } from "@/components/radio/engine/announcements";
import { RECOVERY_POLL_MS, STALL_CHECK_MS, recoveryOutcome, stalled } from "@/components/radio/engine/recovery";

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

  const activeAnnouncementRef = useRef<ActiveAnnouncement | null>(null);
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
    setParamNow(gain.gain, value, ctx.currentTime);
  };

  const rampGain = (slot: Slot, to: number, durationMs: number) => {
    const gain = getGain(slot);
    const ctx = audioCtxRef.current;
    if (!gain || !ctx) return;
    rampParam(gain.gain, to, durationMs, ctx.currentTime);
  };

  const loadDirect = (track: RadioTrackInfo, positionSeconds: number, playing: boolean, gainValue: number) => {
    const slot = activeSlotRef.current;
    const el = getAudioEl(slot);
    if (!el) return;
    slotTrackIdRef.current[slot] = track.id;
    lastProgressRef.current[slot] = Date.now();
    el.src = getApiUrl(`/radio/tracks/${track.id}/stream`);
    el.load();
    setGainNow(slot, gainValue);
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

  const startCrossfade = (nextTrack: RadioTrackInfo, volumePercent: number, seconds: number) => {
    if (crossfadingRef.current) return;
    const fromSlot = activeSlotRef.current;
    const toSlot = otherSlot(fromSlot);
    const toEl = getAudioEl(toSlot);
    if (!toEl || !audioCtxRef.current) return;
    crossfadingRef.current = true;
    slotTrackIdRef.current[toSlot] = nextTrack.id;
    lastProgressRef.current[toSlot] = Date.now();
    toEl.src = getApiUrl(`/radio/tracks/${nextTrack.id}/stream`);
    toEl.currentTime = 0;
    setGainNow(toSlot, 0);
    toEl.play().catch(() => {});
    const durationMs = crossfadeDurationMs(seconds);
    rampGain(fromSlot, 0, durationMs);
    rampGain(toSlot, volumePercent / 100, durationMs);
  };

  const abortCrossfadeIfAny = (restoreVolumePercent: number) => {
    if (!crossfadingRef.current) return;
    const idle = otherSlot(activeSlotRef.current);
    getAudioEl(idle)?.pause();
    setGainNow(idle, 0);
    setGainNow(activeSlotRef.current, restoreVolumePercent / 100);
    slotTrackIdRef.current[idle] = null;
    crossfadingRef.current = false;
  };

  const applyAnnouncement = (evt: RadioEvent) => {
    const data = evt.data;
    const announcementAudio = announcementAudioRef.current;
    const ann = data.current_announcement;
    const wasAnnouncing = activeAnnouncementRef.current;
    if (!announcementAudio) return;
    const plan = planAnnouncement(wasAnnouncing, ann, data.volume, duckSettingsRef.current);
    const annGain = announcementGainRef.current;
    const ctx = audioCtxRef.current;
    if (plan.kind === "start" && ann) {
      activeAnnouncementRef.current = { id: ann.id, mode: ann.mode };
      abortCrossfadeIfAny(data.volume);
      if (announcementFadeOutTimeoutRef.current) {
        clearTimeout(announcementFadeOutTimeoutRef.current);
        announcementFadeOutTimeoutRef.current = null;
      }
      announcementAudio.src = getApiUrl(`/radio/announcements/${ann.id}/stream`);
      announcementAudio.load();
      if (unlocked) announcementAudio.play().catch(() => {});
      const [from, to] = plan.announcementGain;
      if (annGain && ctx) rampParamFrom(annGain.gain, from, to, plan.fadeMs, ctx.currentTime);
      if (plan.musicRamp !== null) rampGain(activeSlotRef.current, plan.musicRamp, plan.fadeMs);
    } else if (plan.kind === "end") {
      activeAnnouncementRef.current = null;
      if (annGain && ctx) rampParam(annGain.gain, plan.announcementGain[1], plan.unloadAfterMs, ctx.currentTime);
      announcementFadeOutTimeoutRef.current = setTimeout(() => {
        unloadMedia(announcementAudio);
        announcementFadeOutTimeoutRef.current = null;
      }, plan.unloadAfterMs);
      if (plan.musicRamp !== null) rampGain(activeSlotRef.current, plan.musicRamp, plan.unloadAfterMs);
    }
  };

  const syncSameTrack = (evt: RadioEvent, ducking: boolean) => {
    const data = evt.data;
    const slot = activeSlotRef.current;
    const el = getAudioEl(slot);
    if (!el) return;
    const duck = duckSettingsRef.current;
    const transport = transportAction(evt.cause, data.current_announcement, data.playing, el.paused, crossfadingRef.current);
    if (transport.abortCrossfade) abortCrossfadeIfAny(ducking ? duck.level : data.volume);
    const gain = targetGain("same", ducking, data.volume, duck);
    if (gain !== null) setGainNow(slot, gain);
    const { seek, action } = transport;
    if (seek) {
      try {
        el.currentTime = data.position_seconds;
      } catch {
      }
    }
    if (action === "play" && unlocked) el.play().catch(() => {});
    else if (action === "pause") el.pause();
  };

  const promoteCrossfadeSlot = (playing: boolean, gain: number) => {
    const fromSlot = activeSlotRef.current;
    const toSlot = otherSlot(fromSlot);
    setGainNow(fromSlot, 0);
    setGainNow(toSlot, gain);
    getAudioEl(fromSlot)?.pause();
    activeSlotRef.current = toSlot;
    crossfadingRef.current = false;
    const newEl = getAudioEl(toSlot);
    if (newEl && !playing && !newEl.paused) newEl.pause();
  };

  const handleEvent = (evt: RadioEvent) => {
    setLastCause(evt.cause);
    applyAnnouncement(evt);
    const data = evt.data;
    const ducking = activeAnnouncementRef.current?.mode === "duck";
    const track = data.current_track;
    const decks = { active: activeSlotRef.current, trackIds: slotTrackIdRef.current, crossfading: crossfadingRef.current };
    const decision = decideTrack(track?.id ?? null, decks);
    if (decision === "unload" || !track) {
      for (const slot of [0, 1] as Slot[]) {
        unloadMedia(getAudioEl(slot));
        slotTrackIdRef.current[slot] = null;
      }
      crossfadingRef.current = false;
      return;
    }
    if (decision === "same") return syncSameTrack(evt, ducking);
    const gain = targetGain(decision, ducking, data.volume, duckSettingsRef.current) ?? 0;
    if (decision === "promote") return promoteCrossfadeSlot(data.playing, gain);
    abortCrossfadeIfAny(data.volume);
    loadDirect(track, data.position_seconds || 0, data.playing, gain);
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
    const sound = JSON.parse(soundKey) as RadioState["sound"];
    soundRef.current = sound;
    soundChainRef.current?.apply(sound);
  }, [soundKey]);
  const mixKey = JSON.stringify(state.mix);
  useEffect(() => {
    mixRef.current = clampMix(JSON.parse(mixKey) as RadioState["mix"]);
    mixStageRef.current?.apply(mixRef.current);
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
    const flags = {
      crossfading: crossfadingRef.current,
      graphReady: graphReadyRef.current,
      announcing: Boolean(activeAnnouncementRef.current),
    };
    const nextTrack = crossfadeTarget(state, el, flags);
    if (nextTrack) startCrossfade(nextTrack, state.volume, crossfadeSeconds(state));
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
      const outcome = recoveryOutcome(
        lastProgressRef.current[slot] > attemptStartedAt,
        Date.now() - attemptStartedAt,
        slot === activeSlotRef.current,
        playingRef.current,
        Boolean(activeAnnouncementRef.current),
      );
      if (outcome === "wait") return;
      clearInterval(pollId);
      recoveringRef.current = false;
      if (outcome === "skip") sendCommand("radio_track_ended", { track_id: slotTrackIdRef.current[slot] });
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

  useEffect(() => {
    const id = setInterval(() => {
      const slot = activeSlotRef.current;
      const sinceProgress = Date.now() - lastProgressRef.current[slot];
      if (stalled(playingRef.current, Boolean(activeAnnouncementRef.current), recoveringRef.current, sinceProgress)) {
        attemptRecovery(slot);
      }
    }, STALL_CHECK_MS);
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
        t={t} state={state} connected={connected} livePosition={livePosition}
        sendCommand={sendCommand} handlePlayPause={handlePlayPause}
      />
    </div>
  );
}
