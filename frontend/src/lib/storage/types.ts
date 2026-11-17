export type VolumeKind = "usb" | "sd" | "hdd" | "ssd" | "image" | "other";

export type VolumeState = "present" | "mounted" | "busy" | "ejecting" | "offline" | "formatting";

export type MediaKind = "video" | "audio" | "image" | "subtitle";

export type TransferKind = "video" | "audio_course" | "radio";

export type Verdict = "recommended" | "acceptable" | "discouraged" | "unknown";

export type Tone = "ok" | "warning" | "critical" | "unknown";

export interface Assessment {
  fstype: string;
  verdict: Verdict;
  reason: string;
  notes: string[];
  journal: boolean | null;
  permissions: boolean | null;
  max_file_gib: number | null;
  write_allowed: boolean;
}

export interface LongevityItem {
  id: "read_only" | "noatime" | "noexec" | "safe_eject" | "trim" | "standby" | "smart";
  enabled: boolean;
  status: "applied" | "inactive" | "disabled" | "unavailable";
  reason: string | null;
}

export interface LongevitySettings {
  read_only: boolean;
  noatime: boolean;
  noexec: boolean;
  standby_minutes: number;
  smart_monitor: boolean;
  auto_mount_library: boolean;
}

export interface Health {
  available: boolean;
  reason?: string | null;
  status: Tone;
  warnings: string[];
  temperature_c?: number | null;
  power_on_hours?: number | null;
  wear_percent_used?: number | null;
  bytes_written?: number;
  write_wear?: Tone;
  overall?: Tone;
}

export interface LibraryInfo {
  registered: boolean;
  id?: number;
  nickname?: string | null;
  online?: boolean;
  stats?: { videos: number; audio_tracks: number; radio_tracks: number };
  bytes_written: number;
  wear_level: "ok" | "warning" | "critical";
  settings: LongevitySettings;
}

export interface StorageVolume {
  key: string;
  name: string;
  label: string | null;
  fstype: string | null;
  size_bytes: number | null;
  kind: VolumeKind;
  transport: string | null;
  rotational: boolean | null;
  mounted: boolean;
  mounted_read_only: boolean | null;
  connected: boolean;
  state: VolumeState;
  uuid_known: boolean;
  usage: { total_bytes: number; free_bytes: number } | null;
  assessment: Assessment;
  can_register: boolean;
  register_block: string | null;
  library: LibraryInfo | null;
  health: Health | null;
  longevity: LongevityItem[];
  standby: { ok: boolean; error?: string } | null;
}

export interface VolumeListing {
  volumes: StorageVolume[];
  recent_removals: Array<{ key: string; name: string; abrupt: boolean }>;
  hidden_count: number;
  encrypted: Array<{ name: string; fstype: string | null }>;
}

export interface PortableDevice {
  id: string;
  name: string;
  scheme: string;
  state: "missing_tool" | "detected" | "ready" | "mounted" | "busy" | "locked" | "needs_approval" | "not_ready";
  hint: string | null;
  install: string | null;
}

export interface PortableListing {
  supported: boolean;
  reason: string | null;
  install?: string | null;
  devices: PortableDevice[];
}

export interface BrowseEntry {
  name: string;
  path: string;
  type: "dir" | "file";
  size: number | null;
  mtime: number | null;
  media: MediaKind | null;
  hidden: boolean;
  indexed?: boolean;
}

export interface BrowseResult {
  path: string;
  parent: string | null;
  entries: BrowseEntry[];
  total: number;
  offset: number;
  limit: number;
  truncated: boolean;
  skipped_links: number;
  portable: boolean;
}

export interface TransferStart {
  job_id: string | null;
  files: number;
  bytes?: number;
  skipped: Array<{ path: string; reason: string }>;
  truncated: boolean;
}

export interface ImportJob {
  id: string;
  kind: string;
  source: string;
  stage: string;
  error: string | null;
  progress_percent: number | null;
  bytes_total?: number | null;
  bytes_done?: number | null;
  files_total?: number | null;
  files_done?: number | null;
  current_file?: string | null;
  details?: { imported?: number; indexed?: number; exported?: number; failed?: Array<{ path: string; message: string }>; skipped?: Array<{ path: string; reason: string }> } | null;
}

export interface FormatAdvice {
  fstype: string;
  reason: string;
  notes: string[];
  host_os: string;
  other_oses: string[];
  procedures: Record<string, string[]>;
  alternatives: Array<{ fstype: string; reason: string }>;
  destructive: boolean;
}
