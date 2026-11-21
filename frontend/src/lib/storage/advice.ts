import type { Assessment } from "./types.ts";

export const OS_CHOICES = ["linux", "windows", "macos", "android"] as const;

export type OsChoice = (typeof OS_CHOICES)[number];

export function adviceQuery(host: OsChoice | null, others: OsChoice[], media: "flash" | "ssd" | "hdd", legacy: boolean): string {
  const params = new URLSearchParams(host ? { host, media } : { media });
  const list = others.filter((o) => o !== host);
  if (list.length) params.set("others", list.join(","));
  if (legacy) params.set("legacy", "true");
  return `?${params.toString()}`;
}

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

export function visibleNotes(assessment: Pick<Assessment, "reason" | "notes">, limit = 3): string[] {
  const redundant: Record<string, string[]> = {
    exfat_no_journal: ["no_journal_unplug_risk", "prefer_read_only"],
    fat_limits: ["file_limit_4gib"],
    exfat_travel: ["no_file_limit"],
    linux_only: ["journal_unplug_ok", "unix_permissions", "no_file_limit"],
    windows_only: ["journal_unplug_ok", "no_file_limit"],
    dirty: ["dirty_repair_first"],
    not_readable_elsewhere: ["not_readable_elsewhere"],
  };
  const skip = new Set(redundant[assessment.reason] ?? []);
  return assessment.notes.filter((n) => !skip.has(n)).slice(0, limit);
}
