/** Formats d'affichage partagés par les écrans : positions de lecture, durées, heure murale. */

/** Position de lecture `m:ss` ; `--:--` quand elle est inconnue. */
export function formatTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** Durée d'un média `m:ss` ; `--:--` quand elle est absente ou nulle. */
export function formatMediaDuration(seconds: number | null | undefined): string {
  return seconds ? formatTime(seconds) : "--:--";
}

/** Durée arrondie à la minute (`42 min`) ; `empty` quand elle est absente ou nulle. */
export function formatMinutes(seconds: number | null | undefined, empty = ""): string {
  return seconds ? `${Math.round(seconds / 60)} min` : empty;
}

/** Heure murale `HH:MM` ; `--:--` sans date. */
export function formatWallClock(date: Date | null): string {
  if (!date) return "--:--";
  return `${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
}
