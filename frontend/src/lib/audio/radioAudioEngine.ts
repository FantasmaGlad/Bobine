import type { RadioRoute } from "../audioRoute.ts";
import { defaultMix, type RadioMix } from "../radioMix.ts";
import { createMixStage, type MixStage } from "../radioMixGraph.ts";
import { defaultSound, soundNeedsLimiter, type RadioSoundSettings } from "../radioSound.ts";
import { createSoundChain, type SoundChain } from "../radioSoundGraph.ts";
import { createPlaybackAudioContext } from "./context.ts";
import { clampUnitGain, createNativeFader, type NativeFader } from "./nativeGain.ts";
import { rampParamLinear, rampParamLinearFrom, setParamImmediate } from "./params.ts";
import { needsWebAudioGraph } from "./radioGraphPolicy.ts";

export type RadioSlot = 0 | 1;

export interface RadioAudioElements {
  getSlot: (slot: RadioSlot) => HTMLAudioElement | null;
  getAnnouncement: () => HTMLAudioElement | null;
  onGraphReady?: (ctx: AudioContext, stage: MixStage) => void;
  createContext?: () => AudioContext | null;
}

export interface RadioAudioEngine {
  unlock: (activeSlot: RadioSlot, initialGain: number) => void;
  setSlotGain: (slot: RadioSlot, value: number) => void;
  rampSlotGain: (slot: RadioSlot, to: number, durationMs: number) => void;
  rampAnnouncementGain: (from: number | null, to: number, durationMs: number) => void;
  updatePolicy: (sound: RadioSoundSettings, mix: RadioMix, route: RadioRoute | null, meter: boolean) => void;
  getContext: () => AudioContext | null;
  getMixStage: () => MixStage | null;
  isAttached: () => boolean;
  dispose: () => void;
}

interface AttachedGraph {
  ctx: AudioContext;
  mixStage: MixStage;
  soundChain: SoundChain;
  slotGains: [GainNode | null, GainNode | null];
  annGain: GainNode | null;
}

function wireWebAudioGraph(
  ctx: AudioContext,
  elements: RadioAudioElements,
  sound: RadioSoundSettings,
  mix: RadioMix,
  nativeSlots: [NativeFader, NativeFader],
  nativeAnn: NativeFader,
): AttachedGraph {
  const mixStage = createMixStage(ctx, ctx.destination, mix, soundNeedsLimiter(sound));
  const soundChain = createSoundChain(ctx, mixStage.musicInput, sound, { includeLimiter: false });
  const slotGains: [GainNode | null, GainNode | null] = [null, null];
  for (const slot of [0, 1] as RadioSlot[]) {
    const el = elements.getSlot(slot);
    if (!el) continue;
    nativeSlots[slot].cancel();
    const gain = ctx.createGain();
    gain.gain.value = nativeSlots[slot].get();
    el.volume = 1;
    gain.connect(soundChain.input);
    ctx.createMediaElementSource(el).connect(gain);
    slotGains[slot] = gain;
  }
  let annGain: GainNode | null = null;
  const annEl = elements.getAnnouncement();
  if (annEl) {
    nativeAnn.cancel();
    const gain = ctx.createGain();
    gain.gain.value = nativeAnn.get();
    annEl.volume = 1;
    gain.connect(mixStage.announcementsInput);
    ctx.createMediaElementSource(annEl).connect(gain);
    annGain = gain;
  }
  ctx.resume().catch(() => {});
  elements.onGraphReady?.(ctx, mixStage);
  return { ctx, mixStage, soundChain, slotGains, annGain };
}

export function createRadioAudioEngine(elements: RadioAudioElements): RadioAudioEngine {
  let unlocked = false;
  let sound: RadioSoundSettings = defaultSound();
  let mix: RadioMix = defaultMix();
  let route: RadioRoute | null = null;
  let meter = false;
  let graph: AttachedGraph | null = null;

  const nativeSlots: [NativeFader, NativeFader] = [
    createNativeFader(() => elements.getSlot(0), 1),
    createNativeFader(() => elements.getSlot(1), 0),
  ];
  const nativeAnn = createNativeFader(() => elements.getAnnouncement(), 1);

  const maybeAttach = () => {
    if (!unlocked || graph || !needsWebAudioGraph(sound, mix, route, meter)) return;
    const ctx = (elements.createContext ?? createPlaybackAudioContext)();
    if (ctx) graph = wireWebAudioGraph(ctx, elements, sound, mix, nativeSlots, nativeAnn);
  };

  return {
    unlock(activeSlot, initialGain) {
      unlocked = true;
      if (!graph) {
        nativeSlots[activeSlot].set(clampUnitGain(initialGain));
        nativeSlots[activeSlot === 0 ? 1 : 0].set(0);
      }
      maybeAttach();
      graph?.ctx.resume().catch(() => {});
    },
    setSlotGain(slot, value) {
      const clamped = clampUnitGain(value);
      const node = graph?.slotGains[slot];
      if (node && graph) setParamImmediate(node.gain, clamped, graph.ctx.currentTime);
      else nativeSlots[slot].set(clamped);
    },
    rampSlotGain(slot, to, durationMs) {
      const clamped = clampUnitGain(to);
      const node = graph?.slotGains[slot];
      if (node && graph) rampParamLinear(node.gain, clamped, durationMs, graph.ctx.currentTime);
      else nativeSlots[slot].rampTo(clamped, durationMs);
    },
    rampAnnouncementGain(from, to, durationMs) {
      const end = clampUnitGain(to);
      if (graph?.annGain) {
        if (from !== null) rampParamLinearFrom(graph.annGain.gain, clampUnitGain(from), end, durationMs, graph.ctx.currentTime);
        else rampParamLinear(graph.annGain.gain, end, durationMs, graph.ctx.currentTime);
      } else if (from !== null) {
        nativeAnn.rampFrom(from, end, durationMs);
      } else {
        nativeAnn.rampTo(end, durationMs);
      }
    },
    updatePolicy(nextSound, nextMix, nextRoute, nextMeter) {
      sound = nextSound;
      mix = nextMix;
      route = nextRoute;
      meter = nextMeter;
      maybeAttach();
      graph?.soundChain.apply(sound, true);
      graph?.mixStage.apply(mix, true, soundNeedsLimiter(sound));
    },
    getContext: () => graph?.ctx ?? null,
    getMixStage: () => graph?.mixStage ?? null,
    isAttached: () => graph !== null,
    dispose() {
      nativeSlots[0].cancel();
      nativeSlots[1].cancel();
      nativeAnn.cancel();
      graph?.ctx.close().catch(() => {});
      graph = null;
    },
  };
}
