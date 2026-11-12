import { meterLevel, toMixerParams, type MeterId, type RadioMix } from "./radioMix.ts";
import { createSoundChain, setParam, type SoundChain } from "./radioSoundGraph.ts";

export type MeterLevels = Record<MeterId, number>;

export interface MixStage {
  musicInput: AudioNode;
  announcementsInput: AudioNode;
  apply: (mix: RadioMix, smooth?: boolean) => void;
  setRouteMuted: (muted: boolean) => void;
  setMetering: (on: boolean) => void;
  readLevels: () => Partial<MeterLevels>;
}

export function createMixStage(ctx: AudioContext, destination: AudioNode, initial: RadioMix): MixStage {
  const params = toMixerParams(initial);
  const musicBus = ctx.createGain();
  const announcementsBus = ctx.createGain();
  const masterBus = ctx.createGain();
  const limiter = ctx.createDynamicsCompressor();
  const routeGate = ctx.createGain();
  musicBus.connect(masterBus);
  announcementsBus.connect(masterBus);
  masterBus.connect(limiter);
  limiter.connect(routeGate);
  routeGate.connect(destination);

  const announcementsChain: SoundChain = createSoundChain(ctx, announcementsBus, params.announcementsSound);

  const apply = (mix: RadioMix, smooth = true) => {
    const p = toMixerParams(mix);
    const now = ctx.currentTime;
    setParam(musicBus.gain, p.music, now, smooth);
    setParam(announcementsBus.gain, p.announcements, now, smooth);
    setParam(masterBus.gain, p.master, now, smooth);
    setParam(limiter.threshold, p.limiter.threshold, now, smooth);
    setParam(limiter.knee, p.limiter.knee, now, smooth);
    setParam(limiter.ratio, p.limiter.ratio, now, smooth);
    setParam(limiter.attack, p.limiter.attack, now, smooth);
    setParam(limiter.release, p.limiter.release, now, smooth);
    announcementsChain.apply(p.announcementsSound, smooth);
  };
  apply(initial, false);
  routeGate.gain.value = 1;

  const setRouteMuted = (muted: boolean) => setParam(routeGate.gain, muted ? 0 : 1, ctx.currentTime, true);

  let analysers: Array<{ id: MeterId; node: AnalyserNode; source: AudioNode; buffer: Float32Array<ArrayBuffer> }> | null = null;
  const setMetering = (on: boolean) => {
    if (on && !analysers) {
      const taps: Array<[MeterId, AudioNode]> = [["music", musicBus], ["announcements", announcementsBus], ["master", masterBus]];
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

  return { musicInput: musicBus, announcementsInput: announcementsChain.input, apply, setRouteMuted, setMetering, readLevels };
}
