export interface ClockAnchor {
  pos: number;
  at_ms: number;
  rate: number;
  running: boolean;
  epoch?: number;
}

export function anchorPosition(anchor: ClockAnchor, serverNowMs: number): number {
  if (!anchor.running || serverNowMs <= anchor.at_ms) return anchor.pos;
  return anchor.pos + ((serverNowMs - anchor.at_ms) / 1000) * anchor.rate;
}

export function msUntilStart(anchor: ClockAnchor, serverNowMs: number): number {
  if (!anchor.running) return 0;
  return Math.max(0, anchor.at_ms - serverNowMs);
}

export const DRIFT_ENTER_S = 0.08;
export const DRIFT_EXIT_S = 0.03;
export const DRIFT_HARD_SEEK_S = 2.0;
export const MAX_RATE_ADJUST = 0.05;
export const EXPLICIT_SEEK_S = 0.3;
const RATE_GAIN = 0.5;

export type DriftAction = "none" | "rate" | "seek";

export interface DriftPlan {
  action: DriftAction;
  playbackRate: number;
}

export function planDrift(
  drift: number,
  nominalRate: number,
  wasCorrecting: boolean,
  explicit = false,
): DriftPlan {
  const abs = Math.abs(drift);
  if (abs >= DRIFT_HARD_SEEK_S || (explicit && abs >= EXPLICIT_SEEK_S)) {
    return { action: "seek", playbackRate: nominalRate };
  }
  const engage = wasCorrecting ? abs >= DRIFT_EXIT_S : abs >= DRIFT_ENTER_S;
  if (!engage) return { action: "none", playbackRate: nominalRate };
  const adjust = Math.max(-MAX_RATE_ADJUST, Math.min(MAX_RATE_ADJUST, drift * RATE_GAIN));
  return { action: "rate", playbackRate: nominalRate * (1 - adjust) };
}

interface OffsetSample {
  offsetMs: number;
  rttMs: number;
}

export class ClockOffsetEstimator {
  private samples: OffsetSample[] = [];

  private readonly maxSamples: number;

  constructor(maxSamples = 16) {
    this.maxSamples = maxSamples;
  }

  add(clientSendMs: number, serverMs: number, clientRecvMs: number): void {
    const rttMs = clientRecvMs - clientSendMs;
    if (!Number.isFinite(rttMs) || rttMs < 0) return;
    const offsetMs = serverMs - (clientSendMs + clientRecvMs) / 2;
    this.samples.push({ offsetMs, rttMs });
    if (this.samples.length > this.maxSamples) this.samples.shift();
  }

  get count(): number {
    return this.samples.length;
  }

  offsetMs(): number {
    if (this.samples.length === 0) return 0;
    const best = [...this.samples]
      .sort((a, b) => a.rttMs - b.rttMs)
      .slice(0, Math.max(1, Math.ceil(this.samples.length / 2)))
      .map((s) => s.offsetMs)
      .sort((a, b) => a - b);
    const mid = Math.floor(best.length / 2);
    return best.length % 2 ? best[mid] : (best[mid - 1] + best[mid]) / 2;
  }

  bestRttMs(): number | null {
    if (this.samples.length === 0) return null;
    return Math.min(...this.samples.map((s) => s.rttMs));
  }
}
