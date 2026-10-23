/**
 * Client de l'API « Stockage externe » (`/api/storage/*`) et aides PURES (testables, `frontend/tests/`).
 *
 * Même accès que les périphériques (PIN, écran local de confiance) et mêmes erreurs structurées
 * `{"detail": {"code", "message", ...}}` : jamais de 500. Le client n'envoie que des chemins RELATIFS au support.
 */

import { parseApiError, type ApiError, type ApiResult } from "./devicesApi.ts";

export type VolumeKind = "usb" | "sd" | "hdd" | "ssd" | "image" | "other";
export type VolumeState = "present" | "mounted" | "busy" | "ejecting" | "offline";
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

export interface StorageStatus {
  driver: string;
  capabilities: Record<string, { supported: boolean; reason?: string }>;
  ready: boolean;
  error: { code: string; message: string } | null;
  free_local_bytes: number;
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

// ---------------------------------------------------------------------------
// Requêtes
// ---------------------------------------------------------------------------

export function getStorageApiUrl(path: string): string {
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `http://localhost:8001/api/storage${path}`;
  }
  return `/api/storage${path}`;
}

export async function storageRequest<T>(path: string, init?: { method?: string; body?: unknown }): Promise<ApiResult<T>> {
  try {
    const res = await fetch(getStorageApiUrl(path), {
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
    return { ok: false, error: { status: 0, code: "network", message: "", extra: {} } as ApiError };
  }
}

export function importJobsUrl(): string {
  if (typeof window !== "undefined" && window.location.port === "3000") return "http://localhost:8001/api/import-jobs";
  return "/api/import-jobs";
}

export function encodeKey(key: string): string {
  return encodeURIComponent(key);
}

// ---------------------------------------------------------------------------
// Aides pures
// ---------------------------------------------------------------------------

const UNITS = {
  fr: ["o", "Ko", "Mo", "Go", "To"],
  en: ["B", "KB", "MB", "GB", "TB"],
} as const;

/** Taille lisible, en unités décimales (convention des supports de stockage) : « 64 Go », « 1,9 To », « 640 Mo ». */
export function formatBytes(bytes: number | null | undefined, lang: "fr" | "en" = "fr"): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes) || bytes < 0) return "—";
  let value = bytes;
  let unit = 0;
  while (value >= 1000 && unit < UNITS[lang].length - 1) {
    value /= 1000;
    unit += 1;
  }
  const rounded = value >= 100 || unit === 0 ? Math.round(value) : Math.round(value * 10) / 10;
  const text = String(rounded).replace(".", lang === "fr" ? "," : ".");
  return `${text} ${UNITS[lang][unit]}`;
}

/** Icône Material Symbols d'un support. */
export function volumeIcon(kind: VolumeKind): string {
  switch (kind) {
    case "sd": return "sd_card";
    case "hdd": return "hard_drive";
    case "ssd": return "hard_drive_2";
    case "image": return "album";
    case "usb": return "usb";
    default: return "storage";
  }
}

export function portableIcon(scheme: string): string {
  return scheme === "afc" ? "phone_iphone" : "smartphone";
}

export type StatusId = "ready" | "busy" | "ejecting" | "offline" | "attention";

/**
 * État affiché d'un support, en un mot : le vocabulaire « monté / démonté » n'est jamais montré.
 * `attention` : un avertissement de santé ou d'usure mérite d'être vu sans ouvrir les options.
 */
export function volumeStatus(volume: Pick<StorageVolume, "state" | "connected" | "health" | "library">): StatusId {
  if (!volume.connected || volume.state === "offline") return "offline";
  if (volume.state === "ejecting") return "ejecting";
  if (volume.state === "busy") return "busy";
  const tone = overallTone(volume);
  return tone === "warning" || tone === "critical" ? "attention" : "ready";
}

export function statusIcon(id: StatusId): string {
  switch (id) {
    case "ready": return "check_circle";
    case "busy": return "sync";
    case "ejecting": return "eject";
    case "offline": return "link_off";
    case "attention": return "warning";
  }
}

/** Pire état entre la santé lue (SMART) et l'usure comptée par Bobine. */
export function overallTone(volume: Pick<StorageVolume, "health" | "library">): Tone {
  const health = volume.health;
  const smart: Tone = health && health.available ? health.status : "unknown";
  const wear: Tone = volume.library?.wear_level === "critical" ? "critical" : volume.library?.wear_level === "warning" ? "warning" : "ok";
  const order: Record<Tone, number> = { ok: 0, unknown: 0, warning: 1, critical: 2 };
  const worst = Math.max(order[smart], order[wear]);
  return worst === 2 ? "critical" : worst === 1 ? "warning" : smart === "ok" ? "ok" : "unknown";
}

export type PrimaryAction = "explore" | null;

/** UNE action principale par support : explorer ; rien tant qu'il est débranché ou en cours de retrait. */
export function primaryAction(volume: Pick<StorageVolume, "state" | "connected">): PrimaryAction {
  if (!volume.connected || volume.state === "offline" || volume.state === "ejecting") return null;
  return "explore";
}

export interface Crumb {
  label: string | null; // null = racine (le nom du support est affiché par l'appelant)
  path: string;
}

export function breadcrumbs(path: string): Crumb[] {
  const crumbs: Crumb[] = [{ label: null, path: "" }];
  let current = "";
  for (const segment of path.split("/").filter(Boolean)) {
    current = current ? `${current}/${segment}` : segment;
    crumbs.push({ label: segment, path: current });
  }
  return crumbs;
}

export function joinPath(parent: string, name: string): string {
  return parent ? `${parent}/${name}` : name;
}

/** Nature d'import proposée d'après la sélection ; l'utilisateur peut la changer. */
export function suggestKind(selected: Array<Pick<BrowseEntry, "type" | "media">>): TransferKind {
  if (selected.some((e) => e.media === "video")) return "video";
  const files = selected.filter((e) => e.type === "file");
  if (files.length > 0 && files.every((e) => e.media === "audio")) return "radio";
  return "video";
}

export function selectionBytes(selected: Array<Pick<BrowseEntry, "size">>): number {
  return selected.reduce((sum, e) => sum + (e.size ?? 0), 0);
}

/** Une entrée se sélectionne si c'est un dossier ou un média ; le reste (texte, système) n'a pas de case. */
export function isSelectable(entry: Pick<BrowseEntry, "type" | "media">): boolean {
  return entry.type === "dir" || (entry.media !== null && entry.media !== "subtitle");
}

/** Tout ce qu'une page de l'explorateur permet de cocher d'un coup. */
export function selectableEntries(entries: BrowseEntry[]): BrowseEntry[] {
  return entries.filter(isSelectable);
}

export function toggleSelection(selected: string[], path: string): string[] {
  return selected.includes(path) ? selected.filter((p) => p !== path) : [...selected, path];
}

/** Réglages recommandés actifs ? (tout ce qui est activé est appliqué ou en attente du montage ; rien n'est « inactif » par erreur). */
export interface LongevitySummary {
  applied: number;
  unavailable: number;
  disabled: number;
  /** Vrai si aucun réglage n'a été désactivé par l'utilisateur : le support est protégé comme recommandé. */
  recommended: boolean;
}

export function longevitySummary(items: LongevityItem[]): LongevitySummary {
  const count = (status: LongevityItem["status"]) => items.filter((i) => i.status === status).length;
  const disabled = count("disabled");
  return { applied: count("applied"), unavailable: count("unavailable"), disabled, recommended: disabled === 0 };
}

export const STANDBY_CHOICES = [0, 10, 20, 30, 60] as const;

/** Libellé court d'un avertissement de santé (codes de `health.py`). */
export function healthWarningKeys(health: Health | null | undefined): string[] {
  return health && health.available ? health.warnings : [];
}

export interface VolumeDiff {
  added: string[];
  removed: Array<{ name: string; abrupt: boolean }>;
}

/** Branchements et retraits entre deux relectures (les évènements WebSocket ne portent aucun nom). */
export function diffVolumes(previous: StorageVolume[], next: StorageVolume[], abruptKeys: Set<string> = new Set()): VolumeDiff {
  const connected = (list: StorageVolume[]) => new Map(list.filter((v) => v.connected).map((v) => [v.key, v]));
  const before = connected(previous);
  const after = connected(next);
  return {
    added: [...after.values()].filter((v) => !before.has(v.key)).map((v) => v.name),
    removed: [...before.values()].filter((v) => !after.has(v.key)).map((v) => ({ name: v.name, abrupt: abruptKeys.has(v.key) })),
  };
}

export function isFinished(job: Pick<ImportJob, "stage">): boolean {
  return job.stage === "done" || job.stage === "error" || job.stage === "cancelled";
}

export function jobPercent(job: Pick<ImportJob, "progress_percent" | "bytes_done" | "bytes_total">): number | null {
  if (job.progress_percent !== null && job.progress_percent !== undefined) return Math.max(0, Math.min(100, Math.round(job.progress_percent)));
  if (job.bytes_total && job.bytes_done !== null && job.bytes_done !== undefined) return Math.max(0, Math.min(100, Math.round((100 * job.bytes_done) / job.bytes_total)));
  return null;
}

/** Plan de fichier choisi par le conseiller : OS de la machine qui héberge Bobine + OS qui brancheront le support. */
export const OS_CHOICES = ["linux", "windows", "macos", "android"] as const;
export type OsChoice = (typeof OS_CHOICES)[number];

export function adviceQuery(host: OsChoice, others: OsChoice[], media: "flash" | "ssd" | "hdd", legacy: boolean): string {
  const params = new URLSearchParams({ host, media });
  const list = others.filter((o) => o !== host);
  if (list.length) params.set("others", list.join(","));
  if (legacy) params.set("legacy", "true");
  return `?${params.toString()}`;
}

/** Système de fichiers affiché pour un humain : exfat → exFAT, vfat → FAT32 (ou FAT), ntfs → NTFS. */
export function fsLabel(fstype: string | null | undefined): string {
  switch ((fstype ?? "").toLowerCase()) {
    case "exfat": return "exFAT";
    case "vfat": case "fat": case "fat32": return "FAT32";
    case "ntfs": case "ntfs3": return "NTFS";
    case "hfsplus": return "HFS+";
    case "apfs": return "APFS";
    case "": return "—";
    default: return fstype as string;
  }
}
