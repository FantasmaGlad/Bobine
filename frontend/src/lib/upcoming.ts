export interface UpcomingOccurrence {
  schedule_id: number;
  run_at: string;
  title: string | null;
  program: string | null;
  duration_seconds?: number | null;
  thumbnail_path?: string | null;
  override_action: string | null;
}

const DAY_MS = 24 * 60 * 60 * 1000;

export function occurrencesPath(channel: string, now: Date, days = 14): string {
  const end = new Date(now.getTime() + days * DAY_MS);
  return `/schedule/occurrences?start=${now.toISOString()}&end=${end.toISOString()}&channel=${channel}`;
}

export function upcomingOnly<T extends Pick<UpcomingOccurrence, "override_action">>(occurrences: readonly T[], limit: number): T[] {
  return occurrences.filter((occurrence) => occurrence.override_action !== "cancelled").slice(0, limit);
}
