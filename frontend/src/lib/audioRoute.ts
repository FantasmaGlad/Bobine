/**
 * Routage audio d'une sortie radio, côté lecteur (phase 2 des périphériques) — logique PURE et testable.
 *
 * Le serveur publie dans l'état de la sortie radio la route choisie (`RadioRoute` : libellés de la sortie physique
 * telle que le système la nomme). Le lecteur `/radio` la traduit en périphérique de SON navigateur :
 * `AudioContext.setSinkId(deviceId)` après avoir retrouvé le périphérique par son libellé.
 *
 * Ce que ça ne peut pas faire, et que ce module REND VISIBLE au lieu de le masquer (statut rapporté au serveur,
 * affiché dans Périphériques → Routage) :
 *  - `unsupported` : le navigateur n'a pas `AudioContext.setSinkId` (Safari, WebView Android...) ;
 *  - `insecure`    : `setSinkId` exige un contexte sécurisé (HTTPS ou localhost) ;
 *  - `needs_labels`: le navigateur masque les noms des sorties tant qu'une permission média n'a pas été accordée ;
 *  - `no_match`    : aucune sortie du navigateur ne porte ce nom (lecteur sur un autre appareil que la machine) ;
 *  - `error`       : le navigateur a refusé.
 * Dans tous ces cas la musique continue sur la sortie par défaut du navigateur : une route ne coupe JAMAIS la diffusion,
 * sauf si l'administrateur a choisi le repli « couper » ET que la sortie visée est débranchée (`muted`).
 */

export type RouteState = "routed" | "missing" | "unknown";
export type RouteFallback = "default" | "mute";

/** Champ `route` de l'état d'une sortie radio (voir `backend/app/devices/routing.py::player_route_state`). */
export interface RadioRoute {
  key: string;
  label: string;
  /** Noms de la sortie tels que le système les donne (ce que `enumerateDevices()` renvoie comme libellé). */
  match: string[];
  kind: string;
  fallback: RouteFallback;
  state: RouteState;
}

export type RouteStatus =
  | "applied"
  | "default"
  | "muted"
  | "unsupported"
  | "insecure"
  | "needs_labels"
  | "no_match"
  | "missing"
  | "error";

export interface OutputDevice {
  deviceId: string;
  label: string;
}

export interface RouteEnv {
  /** `window.isSecureContext`. */
  secure: boolean;
  /** `typeof AudioContext.prototype.setSinkId === "function"`. */
  canSetSinkId: boolean;
}

export type RoutePlan =
  | { action: "sink"; deviceId: string; status: "applied" }
  | { action: "default"; status: "default" | "missing" }
  | { action: "mute"; status: "muted" }
  | { action: "none"; status: Exclude<RouteStatus, "applied" | "default" | "muted"> };

/** Casse, accents et ponctuation ignorés (miroir de `normalize_label` côté serveur). */
export function normalizeLabel(text: string | null | undefined): string {
  return (text ?? "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** Entrées virtuelles du navigateur qui désignent « la sortie par défaut » : jamais une correspondance. */
const VIRTUAL_IDS = new Set(["default", "communications"]);

export type DeviceMatch = { kind: "found"; deviceId: string } | { kind: "needs_labels" } | { kind: "none" };

/**
 * Retrouve le périphérique du navigateur qui porte un des noms de la route : égalité exacte d'abord, puis inclusion
 * (le navigateur préfixe parfois le nom) à condition qu'elle désigne UN SEUL périphérique — jamais de devinette.
 */
export function matchOutputDevice(devices: OutputDevice[], match: string[]): DeviceMatch {
  const real = devices.filter((d) => !VIRTUAL_IDS.has(d.deviceId));
  if (real.length === 0) return { kind: "none" };
  if (real.every((d) => !d.label)) return { kind: "needs_labels" };
  const wanted = match.map(normalizeLabel).filter(Boolean);
  if (wanted.length === 0) return { kind: "none" };
  const labelled = real.filter((d) => d.label).map((d) => ({ deviceId: d.deviceId, label: normalizeLabel(d.label) }));
  const exact = labelled.filter((d) => wanted.includes(d.label));
  if (exact.length === 1) return { kind: "found", deviceId: exact[0].deviceId };
  if (exact.length > 1) return { kind: "none" };
  const partial = labelled.filter((d) => wanted.some((w) => d.label.includes(w) || w.includes(d.label)));
  return partial.length === 1 ? { kind: "found", deviceId: partial[0].deviceId } : { kind: "none" };
}

/**
 * Décide quoi faire d'une route. `devices` est null tant que la liste du navigateur n'a pas pu être lue.
 * Pure : l'application (setSinkId, sourdine) est faite par l'appelant selon l'action.
 */
export function planRoute(route: RadioRoute | null, env: RouteEnv, devices: OutputDevice[] | null): RoutePlan {
  if (!route) return { action: "default", status: "default" };
  if (route.state === "missing") {
    // La sortie choisie est débranchée : repli voulu par l'administrateur (jouer ailleurs, ou se taire).
    return route.fallback === "mute" ? { action: "mute", status: "muted" } : { action: "default", status: "missing" };
  }
  if (!env.canSetSinkId) return { action: "none", status: "unsupported" };
  if (!env.secure) return { action: "none", status: "insecure" };
  if (devices === null) return { action: "none", status: "error" };
  const found = matchOutputDevice(devices, route.match);
  if (found.kind === "found") return { action: "sink", deviceId: found.deviceId, status: "applied" };
  return { action: "none", status: found.kind === "needs_labels" ? "needs_labels" : "no_match" };
}

/** Deux routes décrivent-elles la même demande ? (l'objet est recréé à chaque évènement d'état). */
export function sameRoute(a: RadioRoute | null, b: RadioRoute | null): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

// ---------------------------------------------------------------------------
// Application dans un AudioContext (dépendances injectables : testable sans navigateur)
// ---------------------------------------------------------------------------

export interface SinkContext {
  sinkId?: string | { type: string };
  setSinkId?: (sinkId: string) => Promise<void>;
}

export interface RouteDeps {
  env: RouteEnv;
  /** Sorties audio du navigateur (`enumerateDevices` filtré sur `audiooutput`) ; rejette si indisponible. */
  listOutputs: () => Promise<OutputDevice[]>;
  /** Coupe / rétablit la sortie du lecteur (repli « couper »). */
  setMuted: (muted: boolean) => void;
}

/**
 * Applique une route à un contexte audio et renvoie le statut à rapporter au serveur. Ne lève jamais : toute erreur du
 * navigateur devient `error` et la lecture continue sur la sortie courante.
 */
export async function applyRoute(ctx: SinkContext | null, route: RadioRoute | null, deps: RouteDeps): Promise<RouteStatus> {
  if (!ctx) return route ? "error" : "default";
  let devices: OutputDevice[] | null = null;
  const needsList = route && route.state !== "missing" && deps.env.canSetSinkId && deps.env.secure;
  if (needsList) {
    try {
      devices = await deps.listOutputs();
    } catch {
      devices = null;
    }
  }
  const plan = planRoute(route, deps.env, devices);
  deps.setMuted(plan.action === "mute");
  if (plan.action === "sink") {
    try {
      if (ctx.sinkId !== plan.deviceId) await ctx.setSinkId?.(plan.deviceId);
    } catch {
      return "error";
    }
  } else if (plan.action === "default" || plan.action === "mute") {
    // Retour à la sortie par défaut, seulement si on l'avait quittée (ne pas toucher à un contexte jamais routé).
    const current = ctx.sinkId;
    const onDefault = current === undefined || current === "" || (typeof current === "object" && current !== null);
    if (!onDefault && deps.env.canSetSinkId && deps.env.secure) {
      try {
        await ctx.setSinkId?.("");
      } catch {
        return "error";
      }
    }
  }
  return plan.status;
}
