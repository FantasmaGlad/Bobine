
import type { Video } from "./types";

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "--:--";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}



export function programGroups(videos: Video[]): { program: string; items: Video[] }[] {
  const programOf = (v: Video) => (v.program && v.program.trim() ? v.program : "");
  return Array.from(new Set(videos.map(programOf)))
    .sort((a, b) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b, "fr", { sensitivity: "base" })))
    .map((program) => ({ program, items: videos.filter((v) => programOf(v) === program) }))
    .filter((group) => group.items.length > 0);
}
