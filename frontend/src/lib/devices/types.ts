export interface CapabilityInfo {
  supported: boolean;
  reason?: string;
}

export type Capabilities = Record<string, CapabilityInfo>;

export interface DevicesStatus {
  local: boolean;
  platform: string;
  driver: string;
  capabilities: Capabilities;
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
