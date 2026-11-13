import type { Tone, Verdict, VolumeKind } from "./storageApi.ts";

export type FormatFs = "ext4" | "exfat" | "vfat" | "ntfs";
export const FORMAT_FILESYSTEMS: readonly FormatFs[] = ["ext4", "exfat", "vfat", "ntfs"];
export type FormatStepId = "unmount" | "recheck" | "table" | "format" | "settle" | "readback" | "mount_ro" | "write_test" | "back_ro" | "health";
export type FormatStepState = "pending" | "running" | "ok" | "warn" | "skipped" | "failed";
export type FormatOutcome = "verified" | "verified_with_warnings" | "unchanged" | "erased_blank" | "partial_unknown" | "unverified";

export interface FormatOption {
  fs: FormatFs;
  available: boolean;
  unavailable: string | null;
  install_package: string | null;
  verdict: Verdict;
  reason: string;
  notes: string[];
  max_file_gib: number | null;
  label_max: number;
  label: string;
  recommended: boolean;
  cluster_bytes: number | null;
}

export interface FormatContentVolume {
  label: string | null;
  fstype: string | null;
  size_bytes: number;
  readable?: boolean;
  files?: number;
  dirs?: number;
  truncated?: boolean;
  bytes_used?: number;
  media?: { video: number; audio: number };
  root?: Array<{ name: string; type: "dir" | "file" }>;
  root_truncated?: boolean;
}

export interface FormatPlan {
  token: string;
  expires_in: number;
  min_wait: number;
  target: {
    key: string; name: string; size_bytes: number; kind: VolumeKind; transport: string | null; vendor: string | null; model: string | null; table: string | null;
    partitions: Array<{ label: string | null; fstype: string | null; size_bytes: number; mounted: boolean }>;
  };
  content: { volumes: FormatContentVolume[]; bytes_used: number };
  erases: { partitions: number; files: number; truncated: boolean; unreadable: boolean };
  recommended: FormatFs;
  options: FormatOption[];
  confirm: { mode: "name" | "serial_tail" | "model" | "word"; expected: string };
  quick_only: boolean;
}

export interface FormatJob {
  job_id: string;
  state: "running" | "done" | "failed" | "cancelled";
  stage: string;
  outcome: FormatOutcome | null;
  percent: number;
  steps: Array<{ id: FormatStepId; state: FormatStepState }>;
  can_cancel: boolean;
  point_of_no_return: boolean;
  error: { code: string; message: string } | null;
  report: {
    ok?: boolean;
    checks?: Array<{ id: string; ok: boolean }>;
    filesystem?: string;
    label?: string;
    size_bytes?: number;
    mounted_read_only?: boolean | null;
    health?: { available: boolean; status?: Tone; reason?: string | null };
    params?: { cluster_bytes?: number; reserved_blocks?: number; free_bytes?: number };
  } | null;
  fs: FormatFs;
  label: string;
}

export function formatTravels(travelsToWindowsOrMac: boolean): string[] {
  return travelsToWindowsOrMac ? ["windows", "macos"] : [];
}

export function defaultFormat(plan: Pick<FormatPlan, "recommended" | "options">): FormatFs | null {
  const options = plan.options.filter((o) => o.available);
  return (options.find((o) => o.fs === plan.recommended) ?? options[0])?.fs ?? null;
}

export function labelProblem(fs: FormatFs, raw: string): "empty" | "too_long" | "chars" | null {
  const text = raw.trim();
  if (!text) return "empty";
  if (/[\x00-\x1f\x7f/\\"]/.test(text)) return "chars";
  if (fs === "vfat" && (/[*?.,;:|+=<>[\]]/.test(text) || !/^[\x20-\x7e]+$/.test(text))) return "chars";
  const limit = fs === "ext4" ? 16 : fs === "ntfs" ? 32 : 11;
  const size = fs === "ext4" ? new TextEncoder().encode(text).length : [...text].length;
  return size > limit ? "too_long" : null;
}

export function reflectionLeft(startedAtMs: number, nowMs: number, waitSeconds: number): number {
  return Math.max(0, Math.ceil(waitSeconds - (nowMs - startedAtMs) / 1000));
}

export interface ConfirmInput {
  typed: string;
  expected: string;
  acknowledged: boolean;
  secondsLeft: number;
  labelOk: boolean;
}

export function canConfirmFormat(input: ConfirmInput): boolean {
  const same = input.typed.normalize("NFC").trim().toLocaleLowerCase() === input.expected.normalize("NFC").trim().toLocaleLowerCase();
  return same && input.typed.trim() !== "" && input.acknowledged && input.secondsLeft <= 0 && input.labelOk;
}

export const FORMAT_STEP_ORDER: readonly FormatStepId[] = ["unmount", "recheck", "table", "format", "settle", "readback", "mount_ro", "write_test", "back_ro", "health"];

export function stepIcon(state: FormatStepState): string {
  return state === "ok" ? "check_circle" : state === "running" ? "progress_activity" : state === "failed" ? "error" : state === "warn" ? "warning" : state === "skipped" ? "remove" : "radio_button_unchecked";
}

export function formatFinished(job: Pick<FormatJob, "state">): boolean {
  return job.state !== "running";
}

export function canLeaveWizard(job: Pick<FormatJob, "state" | "point_of_no_return"> | null): boolean {
  return !job || job.state !== "running";
}

export function refusalKey(code: string): string {
  return `storage.format.refusal.${code}`;
}

export const FORMAT_SESSION_KEYS = ["format_token_missing", "format_token_unknown", "format_token_expired", "format_token_used", "format_token_owner", "format_identity_changed"] as const;

export function needsNewPlan(code: string): boolean {
  return (FORMAT_SESSION_KEYS as readonly string[]).includes(code);
}
