/**
 * Client de l'API « Périphériques » (`/api/devices/*`) et aides PURES (testables, `frontend/tests/`).
 *
 * Toutes les erreurs de l'API sont structurées : `{"detail": {"code", "message", ...}}` — jamais une
 * 500. Les requêtes portent le cookie de session PIN (`credentials: "include"`).
 */

export type AccessState = "disabled" | "pin_not_set" | "pin_required" | "granted";

export interface CapabilityInfo {
  supported: boolean;
  reason?: string;
}

export type Capabilities = Record<string, CapabilityInfo>;

export interface DevicesStatus {
  enabled: boolean;
  pin_set: boolean;
  pin_length: number;
  local: boolean;
  access: AccessState;
  platform: string;
  driver: string;
  session_minutes: number;
  wifi_confirm_seconds: number;
  capabilities?: Capabilities;
  retry_after?: number;
}

export interface PairingStatus {
  pin_set: boolean;
  /** Nombre de chiffres du code d'association (défini par le serveur). */
  code_length: number;
  /** Renvoyé uniquement à l'écran local de la machine. */
  code: string | null;
  seconds_left: number;
}

export interface PairingCode {
  code: string;
  seconds_left: number;
}

export type AudioKind = "internal" | "hdmi" | "usb" | "jack" | "bluetooth" | "virtual" | "other";

export interface AudioDevice {
  id: string;
  name: string;
  description?: string;
  manufacturer?: string;
  kind: AudioKind;
  is_default: boolean;
  volume: number | null;
  muted: boolean | null;
  available: boolean;
  /** Nom personnalisé et masquage choisis dans Bobine (communs à toutes les plateformes). */
  alias?: string | null;
  hidden?: boolean;
}

export interface AudioProfile {
  index: number;
  name: string;
  available: boolean;
  active: boolean;
}

export interface AudioDetails {
  supported: boolean;
  reason?: string;
  id: string;
  name: string;
  alias?: string | null;
  hidden?: boolean;
  state: string;
  channels: number | null;
  channel_map: string[];
  sample_rate: number | null;
  format: string | null;
  latency_ms: number | null;
  card: string | null;
  bus: string;
  api: string;
  codec: string | null;
  profile: AudioProfile | null;
  profiles: AudioProfile[];
  /** -1 (tout à gauche) … +1 (tout à droite) ; null si la sortie n'a pas de balance. */
  balance: number | null;
  level: number | null;
  muted: boolean | null;
}

export interface AudioListing {
  supported: boolean;
  reason?: string;
  devices?: AudioDevice[];
  default_id?: string | null;
}

export interface BluetoothDevice {
  address: string;
  name: string;
  paired: boolean;
  connected: boolean;
  trusted: boolean;
  rssi: number | null;
  kind: string;
  profiles: string[];
  battery: number | null;
}

export interface PendingPairing {
  address: string;
  name: string;
  kind: "confirm" | "authorize";
  passkey: string | null;
}

export interface PairingProgress {
  address: string;
  state: "pairing" | "paired" | "failed";
  error: string | null;
}

export interface BluetoothStatus {
  supported: boolean;
  reason?: string;
  powered?: boolean;
  discovering?: boolean;
  adapter_name?: string;
  devices?: BluetoothDevice[];
  pending_pairing?: PendingPairing | null;
  pairing?: PairingProgress | null;
  permission_required?: boolean;
  permission_message?: string;
}

export interface WifiNetwork {
  ssid: string;
  signal: number;
  security: string;
  band: string;
  known: boolean;
  in_use: boolean;
  ip?: string | null;
}

export interface WifiPendingChange {
  kind: "connect" | "power_off";
  target: string;
  previous: string | null;
  seconds_left: number;
}

export interface WifiStatus {
  supported: boolean;
  reason?: string;
  enabled?: boolean;
  interface?: string | null;
  state?: string;
  transport?: string;
  read_only?: boolean;
  current?: WifiNetwork | null;
  networks?: WifiNetwork[];
  known?: string[];
  pending_change?: WifiPendingChange | null;
}

export interface ApiError {
  status: number;
  code: string;
  message: string;
  extra: Record<string, unknown>;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

export function getDevicesApiUrl(path: string): string {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api/devices${path}`;
  }
  return `/api/devices${path}`;
}

/** Interprète le corps d'une réponse d'erreur (détail structuré, texte ou absent). */
export function parseApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object") {
    const { code, message, ...extra } = detail as Record<string, unknown>;
    return { status, code: typeof code === "string" ? code : "error", message: typeof message === "string" ? message : "", extra };
  }
  return { status, code: "error", message: typeof detail === "string" ? detail : "", extra: {} };
}

export async function devicesRequest<T>(path: string, init?: { method?: string; body?: unknown }): Promise<ApiResult<T>> {
  try {
    const res = await fetch(getDevicesApiUrl(path), {
      method: init?.method ?? (init?.body !== undefined ? "POST" : "GET"),
      headers: init?.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
      credentials: "include",
      cache: "no-store",
    });
    const text = await res.text();
    let json: unknown = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = null;
    }
    if (!res.ok) return { ok: false, error: parseApiError(res.status, json) };
    return { ok: true, data: json as T };
  } catch {
    return { ok: false, error: { status: 0, code: "network", message: "", extra: {} } };
  }
}

export async function getPairingStatus(): Promise<ApiResult<PairingStatus>> {
  return devicesRequest<PairingStatus>("/pairing/status");
}

/** Émet (ou renouvelle) le code d'association : écran local uniquement. */
export async function generatePairingCode(): Promise<ApiResult<PairingCode>> {
  return devicesRequest<PairingCode>("/pairing/generate", { method: "POST" });
}

/** Dit tout de suite si le code saisi est le bon (sans le consommer) : l'erreur s'affiche avant le choix du PIN. */
export async function verifyPairingCode(code: string): Promise<ApiResult<{ ok: boolean }>> {
  return devicesRequest("/pairing/verify", { method: "POST", body: { code } });
}

export async function claimPairingCode(code: string, pin: string): Promise<ApiResult<{ ok: boolean; pin_set: boolean; enabled: boolean; session_minutes: number }>> {
  return devicesRequest("/pairing/claim", { method: "POST", body: { code, pin } });
}

// ---------------------------------------------------------------------------
// Aides pures
// ---------------------------------------------------------------------------

/** Un code PIN valide : exactement `length` chiffres. */
export function isValidPin(pin: string, length = 6): boolean {
  return new RegExp(`^\\d{${length}}$`).test(pin);
}

/** Garde uniquement les chiffres, bornés à `length` (saisie du PIN). */
export function sanitizePin(raw: string, length = 6): string {
  return raw.replace(/\D/g, "").slice(0, length);
}

/** Nombre de barres (0-4) pour un niveau de signal 0-100. */
export function signalBars(signal: number): number {
  if (signal >= 75) return 4;
  if (signal >= 50) return 3;
  if (signal >= 25) return 2;
  return signal > 0 ? 1 : 0;
}

export type WifiConnectPlan = "direct" | "needs_password" | "password_local_only";

/**
 * Comment se connecter à un réseau : directement (déjà enregistré ou ouvert), avec un mot de passe saisi
 * sur l'écran LOCAL, ou impossible à distance (le mot de passe ne se saisit jamais à distance : HTTP en clair).
 */
export function wifiConnectPlan(network: Pick<WifiNetwork, "known" | "security">, local: boolean): WifiConnectPlan {
  if (network.known || !network.security) return "direct";
  return local ? "needs_password" : "password_local_only";
}

/** Appareils Bluetooth séparés en appairés / à portée non appairés ; connectés d'abord. */
export function splitBluetooth(devices: BluetoothDevice[]): { paired: BluetoothDevice[]; nearby: BluetoothDevice[] } {
  const byName = (a: BluetoothDevice, b: BluetoothDevice) => Number(b.connected) - Number(a.connected) || a.name.localeCompare(b.name);
  return {
    paired: devices.filter((d) => d.paired).sort(byName),
    nearby: devices.filter((d) => !d.paired).sort((a, b) => (b.rssi ?? -200) - (a.rssi ?? -200) || a.name.localeCompare(b.name)),
  };
}

/** Icône Material Symbols d'une sortie audio. */
export function audioKindIcon(kind: AudioKind): string {
  switch (kind) {
    case "hdmi": return "settings_input_hdmi";
    case "usb": return "usb";
    case "jack": return "headphones";
    case "bluetooth": return "bluetooth_audio";
    case "virtual": return "memory";
    case "internal": return "speaker";
    default: return "volume_up";
  }
}

/** Icône Material Symbols d'un appareil Bluetooth. */
export function bluetoothKindIcon(kind: string): string {
  switch (kind) {
    case "headphones": return "headphones";
    case "headset": return "headset_mic";
    case "speaker": return "speaker";
    case "keyboard": return "keyboard";
    case "mouse": return "mouse";
    case "gamepad": return "sports_esports";
    case "phone": return "smartphone";
    case "computer": return "computer";
    default: return "bluetooth";
  }
}

/** Compte à rebours de confirmation Wi-Fi : secondes restantes (jamais négatif). */
export function secondsLeft(pending: WifiPendingChange | null | undefined, elapsedSeconds: number): number {
  if (!pending) return 0;
  return Math.max(0, pending.seconds_left - Math.floor(elapsedSeconds));
}

// ---------------------------------------------------------------------------
// Détail d'une sortie audio
// ---------------------------------------------------------------------------

/** Nom affiché d'une sortie : l'alias choisi dans Bobine, sinon le nom du système. */
export function audioDisplayName(device: Pick<AudioDevice, "name" | "alias">): string {
  return device.alias?.trim() || device.name;
}

/** Curseur −100…+100 → balance −1…+1, avec un cran au centre (±4 → 0). */
export function balanceFromSlider(value: number): number {
  const clamped = Math.max(-100, Math.min(100, value));
  return Math.abs(clamped) <= 4 ? 0 : Math.round(clamped) / 100;
}

export function sliderFromBalance(balance: number): number {
  return Math.round(Math.max(-1, Math.min(1, balance)) * 100);
}

export type BalanceSide = "left" | "right" | "center";

/** Côté dominant et pourcentage de l'autre canal : « gauche 100 / droite 60 » se lit « droite à 60 % ». */
export function describeBalance(balance: number): { side: BalanceSide; percent: number } {
  if (Math.abs(balance) < 0.005) return { side: "center", percent: 100 };
  return balance < 0
    ? { side: "left", percent: Math.round((1 - -balance) * 100) }
    : { side: "right", percent: Math.round((1 - balance) * 100) };
}

export function formatSampleRate(rate: number | null | undefined): string {
  if (!rate) return "—";
  return rate % 1000 === 0 ? `${rate / 1000} kHz` : `${(rate / 1000).toFixed(1)} kHz`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return ms >= 100 ? `${Math.round(ms)} ms` : `${ms.toFixed(1)} ms`;
}

/** Disposition des canaux : `FL, FR` → « Stéréo (G, D) » ; 6 canaux → « 6 canaux ». */
export function describeChannels(count: number | null | undefined, map: string[]): string {
  if (!count) return "—";
  const short: Record<string, string> = { FL: "G", FR: "D", FC: "C", LFE: "LFE", RL: "AG", RR: "AD", SL: "G latéral", SR: "D latéral", MONO: "M" };
  const labels = map.map((c) => short[c] ?? c);
  if (count === 1) return "Mono";
  if (count === 2) return labels.length ? `Stéréo (${labels.join(", ")})` : "Stéréo";
  return `${count} canaux`;
}

// ---------------------------------------------------------------------------
// Routage audio par sortie radio (phase 2) et table de mixage (phase 3)
// ---------------------------------------------------------------------------

export type RadioOutputId = "radio_cable" | "radio_network";
export const RADIO_OUTPUTS: RadioOutputId[] = ["radio_cable", "radio_network"];

export interface RoutingRoute {
  sink_id: string;
  key: string;
  label: string;
  kind: AudioKind;
  fallback: "default" | "mute";
}

export interface RoutingPlayer {
  /** Lecteur ouvert sur la machine elle-même (le seul que le serveur peut aider à router). */
  local: boolean;
  primary: boolean;
  /** Dernier résultat rapporté par ce lecteur (`applied`, `unsupported`, `insecure`, `needs_labels`, `no_match`, `muted`…). */
  status: string | null;
}

export interface RoutingServerStatus {
  status: "browser" | "waiting" | "moved" | "unchanged" | "released" | "no_stream" | "ambiguous" | "failed" | "unsupported";
  app?: string;
  detail?: string;
  reason?: string;
}

export interface RoutingOutput {
  channel: RadioOutputId;
  route: RoutingRoute | null;
  state: "default" | "routed" | "missing" | "unknown";
  sink_id: string | null;
  playing: boolean;
  players: RoutingPlayer[];
  server: RoutingServerStatus | null;
}

export interface RoutingView {
  supported: boolean;
  reason: string | null;
  server_mechanism: CapabilityInfo;
  fallbacks: Array<"default" | "mute">;
  outputs: RoutingOutput[];
}

export type RoutingTone = "neutral" | "ok" | "info" | "warn" | "bad";

export interface RoutingSummary {
  tone: RoutingTone;
  /** Clé de texte sous `devices.routing.status.`. */
  key: string;
  /** Seconde ligne éventuelle (ce que le serveur a tenté), même espace de clés. */
  extra?: string;
}

const PLAYER_PROBLEMS: Record<string, string> = {
  unsupported: "unsupported",
  insecure: "insecure",
  needs_labels: "needsLabels",
  no_match: "noMatch",
  error: "error",
};

/**
 * Ce que l'administrateur doit lire d'une route : ce qui s'est RÉELLEMENT passé (rapports des lecteurs, action du
 * serveur), jamais « appliqué » par défaut. Pure et testée.
 */
export function summarizeRouting(output: Pick<RoutingOutput, "route" | "state" | "players" | "server">): RoutingSummary {
  const { route, state, players, server } = output;
  if (!route) return { tone: "neutral", key: "none" };
  if (state === "missing") return { tone: "warn", key: route.fallback === "mute" ? "missingMuted" : "missingDefault" };
  if (players.some((p) => p.status === "applied")) return { tone: "ok", key: "appliedBrowser" };
  if (server && (server.status === "moved" || server.status === "unchanged")) return { tone: "ok", key: "appliedServer" };
  if (players.length === 0) return { tone: "info", key: "noPlayer" };
  const ordered = [...players].sort((a, b) => Number(b.local) - Number(a.local) || Number(b.primary) - Number(a.primary));
  const problem = ordered.map((p) => (p.status ? PLAYER_PROBLEMS[p.status] : undefined)).find(Boolean);
  const extra = server && ["ambiguous", "failed", "no_stream"].includes(server.status)
    ? (server.status === "no_stream" ? "serverNoStream" : server.status === "ambiguous" ? "serverAmbiguous" : "serverFailed")
    : undefined;
  if (problem) return { tone: problem === "error" ? "bad" : "warn", key: problem, extra };
  // Rapports absents (lecteur qui n'a pas encore déverrouillé son audio) ou « par défaut » : en attente.
  return { tone: "info", key: "pending", extra };
}

/** Le navigateur courant cache-t-il les noms de ses sorties audio ? (bouton « autoriser les noms de sortie ») */
export function outputLabelsHidden(devices: Array<{ kind: string; label: string }>): boolean {
  const outputs = devices.filter((d) => d.kind === "audiooutput");
  return outputs.length > 0 && outputs.every((d) => !d.label);
}

export interface MixerOutput {
  channel: RadioOutputId;
  mix: unknown;
  sound: unknown;
  playing: boolean;
}

export interface MixerView {
  outputs: MixerOutput[];
}
