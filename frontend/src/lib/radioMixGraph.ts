import { setParam } from "./audio/params.ts";
import { createSafetyLimiter } from "./audio/safetyLimiter.ts";
import { meterLevel, toMixerParams, type MeterId, type RadioMix } from "./radioMix.ts";
import { createSoundChain, type SoundChain } from "./radioSoundGraph.ts";

export type MeterLevels = Record<MeterId, number>;

export interface MixStage {
  musicInput: AudioNode;
  announcementsInput: AudioNode;
  apply: (mix: RadioMix, smooth?: boolean, protectMusic?: boolean) => void;
  setRouteMuted: (muted: boolean) => void;
  setMetering: (on: boolean) => void;
  readLevels: () => Partial<MeterLevels>;
  isLimiterBypassed: () => boolean;
}

interface MeterTap {
  id: MeterId;
  node: AnalyserNode;
  source: AudioNode;
  buffer: Float32Array<ArrayBuffer>;
}

function createMeterBank(ctx: AudioContext, taps: Array<[MeterId, AudioNode]>) {
  let analysers: MeterTap[] | null = null;
  const setMetering = (on: boolean) => {
    if (on && !analysers) {
      analysers = taps.map(([id, source]) => {
        const node = ctx.createAnalyser();
        node.fftSize = 256;
        source.connect(node);
        return { id, node, source, buffer: new Float32Array(node.fftSize) };
      });
    } else if (!on && analysers) {
      for (const a of analysers) a.source.disconnect(a.node);
      analysers = null;
    }
  };
  const readLevels = (): Partial<MeterLevels> => {
    const levels: Partial<MeterLevels> = {};
    for (const a of analysers ?? []) {
      a.node.getFloatTimeDomainData(a.buffer);
      let peak = 0;
      for (let i = 0; i < a.buffer.length; i++) peak = Math.max(peak, Math.abs(a.buffer[i]));
      levels[a.id] = meterLevel(peak);
    }
    return levels;
  };
  return { setMetering, readLevels };
}

export function createMixStage(
  ctx: AudioContext,
  destination: AudioNode,
  initial: RadioMix,
  initialProtectMusic = false,
): MixStage {
  const params = toMixerParams(initial, initialProtectMusic);
  const musicBus = ctx.createGain();
  const announcementsBus = ctx.createGain();
  const masterBus = ctx.createGain();
  const routeGate = ctx.createGain();
  const safety = createSafetyLimiter(ctx, routeGate, params.limiter);
  musicBus.connect(masterBus);
  announcementsBus.connect(masterBus);
  masterBus.connect(safety.input);
  routeGate.connect(destination);

  const announcementsChain: SoundChain = createSoundChain(
    ctx,
    announcementsBus,
    params.announcementsSound,
    { includeLimiter: false },
  );

  const apply = (mix: RadioMix, smooth = true, protectMusic = false) => {
    const p = toMixerParams(mix, protectMusic);
    const now = ctx.currentTime;
    setParam(musicBus.gain, p.music, now, smooth);
    setParam(announcementsBus.gain, p.announcements, now, smooth);
    setParam(masterBus.gain, p.master, now, smooth);
    safety.apply(p.limiter, now, smooth);
    announcementsChain.apply(p.announcementsSound, smooth);
  };
  apply(initial, false, initialProtectMusic);
  routeGate.gain.value = 1;

  const setRouteMuted = (muted: boolean) => setParam(routeGate.gain, muted ? 0 : 1, ctx.currentTime, true);
  const meters = createMeterBank(ctx, [["music", musicBus], ["announcements", announcementsBus], ["master", masterBus]]);

  return {
    musicInput: musicBus,
    announcementsInput: announcementsChain.input,
    apply,
    setRouteMuted,
    setMetering: meters.setMetering,
    readLevels: meters.readLevels,
    isLimiterBypassed: safety.isBypassed,
  };
}
