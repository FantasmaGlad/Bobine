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
