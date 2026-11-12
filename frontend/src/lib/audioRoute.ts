export type RouteState = "routed" | "missing" | "unknown";
export type RouteFallback = "default" | "mute";

export interface RadioRoute {
  key: string;
  label: string;
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
  secure: boolean;
  canSetSinkId: boolean;
}

export type RoutePlan =
  | { action: "sink"; deviceId: string; status: "applied" }
  | { action: "default"; status: "default" | "missing" }
  | { action: "mute"; status: "muted" }
  | { action: "none"; status: Exclude<RouteStatus, "applied" | "default" | "muted"> };

export function normalizeLabel(text: string | null | undefined): string {
  return (text ?? "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const VIRTUAL_IDS = new Set(["default", "communications"]);

export type DeviceMatch = { kind: "found"; deviceId: string } | { kind: "needs_labels" } | { kind: "none" };

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

export function planRoute(route: RadioRoute | null, env: RouteEnv, devices: OutputDevice[] | null): RoutePlan {
  if (!route) return { action: "default", status: "default" };
  if (route.state === "missing") {
    return route.fallback === "mute" ? { action: "mute", status: "muted" } : { action: "default", status: "missing" };
  }
  if (!env.canSetSinkId) return { action: "none", status: "unsupported" };
  if (!env.secure) return { action: "none", status: "insecure" };
  if (devices === null) return { action: "none", status: "error" };
  const found = matchOutputDevice(devices, route.match);
  if (found.kind === "found") return { action: "sink", deviceId: found.deviceId, status: "applied" };
  return { action: "none", status: found.kind === "needs_labels" ? "needs_labels" : "no_match" };
}

export function sameRoute(a: RadioRoute | null, b: RadioRoute | null): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export interface SinkContext {
  sinkId?: string | { type: string };
  setSinkId?: (sinkId: string) => Promise<void>;
}

export interface RouteDeps {
  env: RouteEnv;
  listOutputs: () => Promise<OutputDevice[]>;
  setMuted: (muted: boolean) => void;
}

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
