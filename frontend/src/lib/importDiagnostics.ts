/**
 * Lecture du diagnostic de la chaîne d'import (`GET /api/diagnostics/import`,
 * backend `app/routers/diagnostics.py`) : types, formatage et traduction des
 * constats. Pur (sans React ni réseau) pour être testé sans navigateur ; le
 * panneau de Réglages (`components/ImportDiagnosticsPanel.tsx`) ne fait que
 * l'afficher.
 *
 * Chaque bloc du rapport peut valoir `{ error }` si le serveur n'a pas pu le
 * calculer : l'affichage dégrade bloc par bloc, jamais en bloc entier.
 */

export interface BlockError { error: string }

export interface ToolState {
  path: string;
  found: boolean;
  executable: boolean;
  version: string | null;
  error: string | null;
}

export interface DirectoryState {
  path: string;
  exists: boolean;
  writable: boolean;
  free_bytes: number | null;
  total_bytes: number | null;
  error?: string;
  partial_uploads?: number;
  partial_bytes?: number;
}

export interface ExecutorState {
  max_workers: number | null;
  threads_started: number;
  threads_alive: number;
  queued: number | null;
  shutdown: boolean;
}

export interface ActiveJob {
  id: string;
  kind: string | null;
  source: string | null;
  stage: string;
  age_seconds: number;
  idle_seconds: number;
  queue_position: number | null;
}

export interface ImportDiagnostics {
  generated_at: number;
  os: string | BlockError;
  frozen: boolean;
  ffmpeg: ToolState | BlockError;
  ffprobe: ToolState | BlockError;
  temp_dir: DirectoryState | BlockError;
  staging_dir: DirectoryState | BlockError;
  media_dir: DirectoryState | BlockError;
  executors: { ffmpeg: ExecutorState; io: ExecutorState } | BlockError;
  jobs: { active: ActiveJob[]; counts: Record<string, number> } | BlockError;
  problems: string[];
}

export function isBlockError(block: unknown): block is BlockError {
  return typeof block === "object" && block !== null && typeof (block as BlockError).error === "string" && !("path" in block);
}

/** Codes de constats renvoyés par le serveur → clé i18n. Un code inconnu (serveur plus récent) est ignoré. */
const PROBLEM_KEYS: Record<string, string> = {
  ffmpeg_unavailable: "settingsPage.importDiag.problems.ffmpeg_unavailable",
  ffprobe_unavailable: "settingsPage.importDiag.problems.ffprobe_unavailable",
  temp_not_writable: "settingsPage.importDiag.problems.temp_not_writable",
  disk_low: "settingsPage.importDiag.problems.disk_low",
  job_stuck: "settingsPage.importDiag.problems.job_stuck",
  executor_shutdown: "settingsPage.importDiag.problems.executor_shutdown",
};

export function problemKeys(problems: string[] | undefined): string[] {
  return (problems ?? []).map((code) => PROBLEM_KEYS[code]).filter((key): key is string => Boolean(key));
}

/** Clé de l'aide d'installation d'ffmpeg pour le système du serveur. */
export function installHintKey(os: unknown): string {
  const known = typeof os === "string" && ["macos", "windows", "linux", "android"].includes(os) ? os : "linux";
  return `uploads.errors.installHint.${known}`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (typeof bytes !== "number" || !isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024 ** 2) return `${Math.round(bytes / 1024)} Ko`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(bytes < 10 * 1024 ** 2 ? 1 : 0)} Mo`;
  return `${(bytes / 1024 ** 3).toFixed(1)} Go`;
}

/** Durée courte : « 45 s », « 12 min », « 3 h 05 ». */
export function formatAge(seconds: number | null | undefined): string {
  if (typeof seconds !== "number" || !isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 90) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h} h ${String(m).padStart(2, "0")}`;
}

/** Texte brut du rapport, à coller dans une demande de support. */
export function reportAsText(report: ImportDiagnostics): string {
  const lines: string[] = [`Bobine — diagnostic d'import (${new Date(report.generated_at * 1000).toISOString()})`];
  const os = isBlockError(report.os) ? "?" : report.os;
  lines.push(`Système : ${os}${report.frozen ? " (application empaquetée)" : ""}`);
  for (const [label, tool] of [["ffmpeg", report.ffmpeg], ["ffprobe", report.ffprobe]] as const) {
    lines.push(isBlockError(tool)
      ? `${label} : indisponible (${tool.error})`
      : `${label} : ${tool.found ? tool.path : "introuvable"}${tool.version ? ` — ${tool.version}` : ""}${tool.error ? ` [${tool.error}]` : ""}`);
  }
  for (const [label, dir] of [["Dossier temporaire", report.temp_dir], ["Transferts en cours", report.staging_dir], ["Dossier des médias", report.media_dir]] as const) {
    lines.push(isBlockError(dir)
      ? `${label} : indisponible (${dir.error})`
      : `${label} : ${dir.path} — ${dir.writable ? "inscriptible" : "NON inscriptible"}, ${formatBytes(dir.free_bytes)} libres${dir.error ? ` [${dir.error}]` : ""}`);
  }
  if (!isBlockError(report.executors)) {
    const e = report.executors.ffmpeg;
    lines.push(`Exécuteur ffmpeg : ${e.threads_alive}/${e.max_workers ?? "?"} thread(s) actif(s), ${e.queued ?? "?"} en attente`);
  }
  if (!isBlockError(report.jobs)) {
    lines.push(`Tâches actives : ${report.jobs.active.length}`);
    for (const j of report.jobs.active) lines.push(`  - ${j.kind ?? "?"} ${j.stage} (âge ${formatAge(j.age_seconds)}, sans mise à jour depuis ${formatAge(j.idle_seconds)})`);
  }
  if (report.problems.length > 0) lines.push(`Constats : ${report.problems.join(", ")}`);
  return lines.join("\n");
}
