/**
 * Chaîne de traitement du son d'une sortie radio, dans le graphe Web Audio du lecteur :
 *
 *   entrée → préampli → 5 bandes → basses → loudness (grave, aigu) → limiteur → sortie
 *
 * Une SEULE chaîne pour toute la musique (les deux slots A/B du fondu enchaîné s'y
 * additionnent) : 9 nœuds au total, quel que soit le nombre de pistes. Les rappels vocaux la
 * CONTOURNENT (ils se branchent directement sur la sortie) pour rester intelligibles.
 *
 * Les paramètres viennent de `toGraphParams` (logique pure, testée). Le graphe n'est jamais
 * reconnecté en cours de lecture : le « son neutre » met simplement tous les filtres à 0 dB.
 * Les changements sont lissés (`setTargetAtTime`) pour éviter les craquements de réglage.
 */
// Import relatif avec extension (et non l'alias @/) : ce module est aussi chargé tel quel par le
// lanceur de tests Node (`npm test`), qui ne résout pas les alias de chemins.
import { toGraphParams, type FilterParams, type RadioSoundSettings } from "./radioSound.ts";

/** Constante de temps (s) du lissage des changements de paramètres. */
const SMOOTHING_TIME_CONSTANT = 0.03;

export interface SoundChain {
  /** Nœud où brancher la musique (sortie des gains des slots). */
  input: AudioNode;
  /** Applique des réglages; `smooth=false` pour l'état initial (pas de transition audible). */
  apply: (sound: RadioSoundSettings, smooth?: boolean) => void;
}

export function setParam(param: AudioParam, value: number, now: number, smooth: boolean): void {
  param.cancelScheduledValues(now);
  if (smooth) param.setTargetAtTime(value, now, SMOOTHING_TIME_CONSTANT);
  else param.setValueAtTime(value, now);
}

function createFilter(ctx: AudioContext, params: FilterParams): BiquadFilterNode {
  const node = ctx.createBiquadFilter();
  node.type = params.type;
  node.frequency.value = params.frequency;
  node.Q.value = params.q;
  node.gain.value = 0;
  return node;
}

export function createSoundChain(ctx: AudioContext, destination: AudioNode, initial: RadioSoundSettings): SoundChain {
  const neutral = toGraphParams(initial);
  const preamp = ctx.createGain();
  const bandNodes = neutral.bands.map((band) => createFilter(ctx, band));
  const bass = createFilter(ctx, neutral.bass);
  const loudnessLow = createFilter(ctx, neutral.loudnessLow);
  const loudnessHigh = createFilter(ctx, neutral.loudnessHigh);
  const limiter = ctx.createDynamicsCompressor();

  const chain: AudioNode[] = [preamp, ...bandNodes, bass, loudnessLow, loudnessHigh, limiter];
  for (let i = 0; i < chain.length - 1; i++) chain[i].connect(chain[i + 1]);
  limiter.connect(destination);

  const apply = (sound: RadioSoundSettings, smooth = true) => {
    const p = toGraphParams(sound);
    const now = ctx.currentTime;
    setParam(preamp.gain, p.preampGain, now, smooth);
    p.bands.forEach((band, i) => setParam(bandNodes[i].gain, band.gain, now, smooth));
    setParam(bass.gain, p.bass.gain, now, smooth);
    setParam(loudnessLow.gain, p.loudnessLow.gain, now, smooth);
    setParam(loudnessHigh.gain, p.loudnessHigh.gain, now, smooth);
    setParam(limiter.threshold, p.limiter.threshold, now, smooth);
    setParam(limiter.knee, p.limiter.knee, now, smooth);
    setParam(limiter.ratio, p.limiter.ratio, now, smooth);
    setParam(limiter.attack, p.limiter.attack, now, smooth);
    setParam(limiter.release, p.limiter.release, now, smooth);
  };

  apply(initial, false);
  return { input: preamp, apply };
}
