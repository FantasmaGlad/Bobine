/**
 * Côté client de l'horloge de lecture serveur —
 * logique PURE (aucun accès au DOM) pour rester testable (`frontend/tests/`).
 *
 * Le serveur publie une ancre `{ pos, at_ms, rate, running }` : « à l'instant
 * serveur `at_ms`, la position était `pos` ; si `running`, elle avance à `rate`
 * depuis cet instant ». Chaque écran en déduit LOCALEMENT la position cible à
 * tout instant, puis ramène son <video> dessus :
 *   - dérive faible  -> rien ;
 *   - dérive moyenne -> `playbackRate` légèrement ajusté (±5 %, imperceptible,
 *     SANS `seek`, donc sans reset du pipeline de décodage matériel) ;
 *   - dérive forte   -> UN seul `seek` (changement de média, longue mise en
 *     mémoire tampon...).
 * C'est ce qui remplace les `seek` répétés qui figeaient MediaCodec/VA-API.
 */

export interface ClockAnchor {
  /** Position (s) à l'instant `at_ms`. */
  pos: number;
  /** Instant serveur (epoch, ms) de l'ancre ; peut être FUTUR (démarrage synchronisé). */
  at_ms: number;
  rate: number;
  running: boolean;
  /** Incrémenté par le serveur à chaque ordre (play, pause, seek, vitesse,
   * chargement, arrêt) ; absent d'un backend plus ancien. */
  epoch?: number;
}

/** Position cible (s) à l'instant serveur `serverNowMs`. */
export function anchorPosition(anchor: ClockAnchor, serverNowMs: number): number {
  if (!anchor.running || serverNowMs <= anchor.at_ms) return anchor.pos;
  return anchor.pos + ((serverNowMs - anchor.at_ms) / 1000) * anchor.rate;
}

/** Millisecondes avant l'instant de départ ; 0 s'il est passé ou si à l'arrêt. */
export function msUntilStart(anchor: ClockAnchor, serverNowMs: number): number {
  if (!anchor.running) return 0;
  return Math.max(0, anchor.at_ms - serverNowMs);
}

// Seuils de la correction (secondes). Hystérésis : on entre en correction
// au-delà de ENTER et on n'en sort qu'en dessous de EXIT, pour ne pas osciller
// autour d'une valeur unique.
export const DRIFT_ENTER_S = 0.08;
export const DRIFT_EXIT_S = 0.03;
export const DRIFT_HARD_SEEK_S = 2.0;
export const MAX_RATE_ADJUST = 0.05;
// Après un ORDRE explicite (seek/play/chargement), au-delà de cet écart on
// replace tout de suite le média sur la position demandée : l'utilisateur veut
// la position exacte, pas une convergence progressive par la vitesse.
export const EXPLICIT_SEEK_S = 0.3;
const RATE_GAIN = 0.5;

export type DriftAction = "none" | "rate" | "seek";

export interface DriftPlan {
  action: DriftAction;
  /** `playbackRate` à appliquer (ignoré pour "seek", qui garde la vitesse nominale). */
  playbackRate: number;
}

/**
 * @param drift          position du média − position cible (s) ; > 0 = en avance.
 * @param nominalRate    vitesse choisie par l'utilisateur (ancre.rate).
 * @param wasCorrecting  une correction de vitesse était déjà en cours.
 * @param explicit       la dérive vient d'un ORDRE (changement d'epoch), pas d'un
 *                       décrochage : seek immédiat dès 0,3 s d'écart.
 */
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

/**
 * Estimation du décalage entre l'horloge locale et l'horloge serveur, façon
 * NTP : pour chaque aller-retour, `offset = serveur − (envoi + réception)/2`.
 * Seuls les échantillons au plus petit RTT sont retenus (un RTT court borne
 * l'erreur à RTT/2 : quelques ms en LAN), puis on prend la médiane.
 */
export class ClockOffsetEstimator {
  private samples: OffsetSample[] = [];

  // Pas de « parameter property » TypeScript : le lanceur de tests Node
  // (strip-types) ne les transforme pas.
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

  /** `serveur − local` (ms), 0 tant qu'aucun échantillon n'est arrivé. */
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

  /** Plus petit RTT observé (ms) — mesure de confiance, null si aucun échantillon. */
  bestRttMs(): number | null {
    if (this.samples.length === 0) return null;
    return Math.min(...this.samples.map((s) => s.rttMs));
  }
}
