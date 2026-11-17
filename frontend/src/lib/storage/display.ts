import type { Health, ImportJob, LongevityItem, StorageVolume, Tone, VolumeKind } from "./types.ts";

const UNITS = {
  fr: ["o", "Ko", "Mo", "Go", "To"],
  en: ["B", "KB", "MB", "GB", "TB"],
} as const;

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

export function volumeStatus(volume: Pick<StorageVolume, "state" | "connected" | "health" | "library">): StatusId {
  if (!volume.connected || volume.state === "offline") return "offline";
  if (volume.state === "ejecting") return "ejecting";
  if (volume.state === "busy" || volume.state === "formatting") return "busy";
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

export function overallTone(volume: Pick<StorageVolume, "health" | "library">): Tone {
  const health = volume.health;
  const smart: Tone = health && health.available ? health.status : "unknown";
  const wear: Tone = volume.library?.wear_level === "critical" ? "critical" : volume.library?.wear_level === "warning" ? "warning" : "ok";
  const order: Record<Tone, number> = { ok: 0, unknown: 0, warning: 1, critical: 2 };
  const worst = Math.max(order[smart], order[wear]);
  return worst === 2 ? "critical" : worst === 1 ? "warning" : smart === "ok" ? "ok" : "unknown";
}

export type PrimaryAction = "explore" | null;

export function primaryAction(volume: Pick<StorageVolume, "state" | "connected">): PrimaryAction {
  if (!volume.connected || volume.state === "offline" || volume.state === "ejecting" || volume.state === "formatting") return null;
  return "explore";
}

export interface LongevitySummary {
  applied: number;
  unavailable: number;
  disabled: number;
  recommended: boolean;
}

export function longevitySummary(items: LongevityItem[]): LongevitySummary {
  const count = (status: LongevityItem["status"]) => items.filter((i) => i.status === status).length;
  const disabled = count("disabled");
  return { applied: count("applied"), unavailable: count("unavailable"), disabled, recommended: disabled === 0 };
}

export const STANDBY_CHOICES = [0, 10, 20, 30, 60] as const;

export function healthWarningKeys(health: Health | null | undefined): string[] {
  return health && health.available ? health.warnings : [];
}

export interface VolumeDiff {
  added: string[];
  removed: Array<{ name: string; abrupt: boolean }>;
}

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
